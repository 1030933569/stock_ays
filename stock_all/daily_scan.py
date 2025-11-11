"""
日线触发信号扫描器
- 基于周线观察池，检测日线买入时机
- 识别突破型和回踩型触发信号
- 计算入场价、止损价、风险收益比

使用方法:
    python stock_all/daily_scan.py --config stock_all/config.yaml --watchlist output/watchlist.csv
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml
from tqdm import tqdm

# 导入自定义模块
from indicators import (
    calculate_all_indicators,
    find_support_resistance,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="日线触发信号扫描器")
    parser.add_argument(
        "--config",
        default="stock_all/config.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--watchlist",
        required=True,
        help="观察池文件路径（weekly_scan.py的输出）",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="K线数据目录（覆盖配置文件中的设置）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出文件路径（覆盖配置文件中的设置）",
    )
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def load_kline_data(stock_code: str, data_dir: Path, freq: str) -> Optional[pd.DataFrame]:
    """
    加载K线数据
    
    Args:
        stock_code: 股票代码（如 600000）
        data_dir: 数据目录
        freq: 频率 'daily', 'weekly', 'monthly'
        
    Returns:
        K线数据DataFrame或None
    """
    # 确保stock_code是字符串类型
    stock_code = str(stock_code)
    
    freq_map = {
        'daily': '_daily_1y.csv',
        'weekly': '_weekly_5y.csv',
        'monthly': '_monthly_10y.csv'
    }
    
    file_path = data_dir / stock_code / f"{stock_code}{freq_map[freq]}"
    
    if not file_path.exists():
        return None
    
    try:
        df = pd.read_csv(file_path)
        if df.empty:
            return None
        
        # 确保按日期排序
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        return None


def detect_breakout_trigger(daily_df: pd.DataFrame, weekly_pivot: float, config: dict) -> Optional[dict]:
    """
    检测突破型触发信号
    
    Args:
        daily_df: 日线数据（已计算指标）
        weekly_pivot: 周线枢轴价（关键阻力位）
        config: 配置参数
        
    Returns:
        触发信号字典或None
    """
    params = config['daily']['breakout']
    
    if len(daily_df) < 20:
        return None
    
    latest = daily_df.iloc[-1]
    
    # 1. 价格突破枢轴
    if latest['close'] <= weekly_pivot:
        return None
    
    # 检查是否是近期突破（最近3天内）
    recent_3d = daily_df.tail(3)
    breakthrough = False
    for i in range(len(recent_3d)):
        if recent_3d.iloc[i]['close'] > weekly_pivot:
            # 检查前一天是否在枢轴下方
            if i == 0:
                prev_close = daily_df.iloc[-4]['close'] if len(daily_df) >= 4 else 0
                if prev_close <= weekly_pivot:
                    breakthrough = True
            else:
                if recent_3d.iloc[i-1]['close'] <= weekly_pivot:
                    breakthrough = True
    
    if not breakthrough:
        return None
    
    # 2. 成交量放大
    if 'volume_ratio' in latest and not pd.isna(latest['volume_ratio']):
        if latest['volume_ratio'] < params['volume_ratio_min']:
            return None
    
    # 3. RSI确认或创新高
    signal_strength = 0
    
    if 'RSI' in latest and not pd.isna(latest['RSI']):
        if latest['RSI'] > params['rsi_threshold']:
            signal_strength += 1
    
    # 检查是否创N日新高
    lookback_high = daily_df.tail(params['new_high_days'])['high'].max()
    if latest['close'] >= lookback_high:
        signal_strength += 1
    
    if signal_strength == 0:
        return None
    
    return {
        'trigger_type': 'BREAKOUT',
        'signal_strength': signal_strength,
        'volume_ratio': latest.get('volume_ratio', 0),
        'rsi': latest.get('RSI', 0),
    }


def detect_pullback_trigger(daily_df: pd.DataFrame, config: dict) -> Optional[dict]:
    """
    检测回踩型触发信号
    
    Args:
        daily_df: 日线数据（已计算指标）
        config: 配置参数
        
    Returns:
        触发信号字典或None
    """
    params = config['daily']['pullback']
    
    if len(daily_df) < params['lookback_days'] + 5:
        return None
    
    latest = daily_df.iloc[-1]
    recent = daily_df.tail(params['lookback_days'])
    
    # 1. 检查是否回踩均线
    ma_support_found = False
    support_ma = None
    
    for ma_period in params['ma_support']:
        ma_col = f'MA{ma_period}'
        if ma_col not in daily_df.columns:
            continue
        
        # 检查最近几天是否触及或接近该均线（±2%）
        for i in range(max(1, len(recent) - 5), len(recent)):
            row = recent.iloc[i]
            if pd.isna(row[ma_col]):
                continue
            
            # 低点接近均线
            distance = abs(row['low'] - row[ma_col]) / row[ma_col]
            if distance < 0.02:  # 2%以内
                ma_support_found = True
                support_ma = ma_period
                break
        
        if ma_support_found:
            break
    
    if not ma_support_found:
        return None
    
    # 2. 检查回踩时量能萎缩
    # 找到回踩的那几天
    pullback_days = recent.tail(5)
    pullback_avg_volume = pullback_days['volume'].mean()
    overall_avg_volume = recent['volume'].mean()
    
    # 回踩时量能应该小于整体均量
    if pullback_avg_volume > overall_avg_volume * params['volume_shrink_ratio']:
        return None
    
    # 3. 今日放量收复
    if latest['close'] <= latest['open']:  # 不是阳线
        return None
    
    if 'volume_ratio' in latest and not pd.isna(latest['volume_ratio']):
        if latest['volume_ratio'] < params['recovery_volume_ratio']:
            return None
    
    # 4. 最大回撤检查
    max_price = recent['high'].max()
    min_price = recent['low'].min()
    drawdown = (max_price - min_price) / max_price
    
    if drawdown > params['max_drawback_pct']:
        return None
    
    # 5. 计算信号强度
    signal_strength = 1
    
    # 如果今日收盘价突破最近5天高点，加分
    if latest['close'] > recent.tail(5).iloc[:-1]['high'].max():
        signal_strength += 1
    
    return {
        'trigger_type': 'PULLBACK',
        'signal_strength': signal_strength,
        'support_ma': support_ma,
        'volume_ratio': latest.get('volume_ratio', 0),
        'drawdown': drawdown,
    }


def calculate_stop_loss(daily_df: pd.DataFrame, entry_price: float, config: dict) -> tuple[float, float]:
    """
    计算止损价和风险百分比
    
    Args:
        daily_df: 日线数据
        entry_price: 入场价
        config: 配置参数
        
    Returns:
        (止损价, 风险百分比)
    """
    params = config['daily']['stop_loss']
    
    # 方法1: 初始百分比止损
    stop1 = entry_price * (1 - params['initial_pct'])
    
    # 方法2: ATR止损
    stop2 = entry_price
    if 'ATR' in daily_df.columns:
        latest_atr = daily_df.iloc[-1]['ATR']
        if not pd.isna(latest_atr):
            stop2 = entry_price - latest_atr * params['atr_multiplier']
    
    # 方法3: 结构低点
    stop3 = entry_price
    if params['use_structure_low']:
        recent_20d = daily_df.tail(20)
        structure_low = recent_20d['low'].min()
        stop3 = structure_low * 0.99  # 略低于结构低点
    
    # 取最高的止损价（最保守）
    stop_loss = max(stop1, stop2, stop3)
    
    # 确保止损价合理（不超过10%）
    if (entry_price - stop_loss) / entry_price > 0.10:
        stop_loss = entry_price * 0.90
    
    risk_pct = (entry_price - stop_loss) / entry_price
    
    return stop_loss, risk_pct


def process_single_stock(stock_code: str, data_dir: Path, weekly_info: dict, config: dict) -> Optional[dict]:
    """
    处理单只股票，检测日线触发信号
    
    Args:
        stock_code: 股票代码
        data_dir: 数据目录
        weekly_info: 周线筛选结果（包含ma40_weekly等）
        config: 配置参数
        
    Returns:
        信号字典或None
    """
    # 1. 加载日线和周线数据
    daily_df = load_kline_data(stock_code, data_dir, 'daily')
    weekly_df = load_kline_data(stock_code, data_dir, 'weekly')
    
    if daily_df is None or weekly_df is None:
        return None
    
    # 2. 计算日线指标
    daily_df = calculate_all_indicators(daily_df, freq='daily')
    
    if len(daily_df) < 60:
        return None
    
    # 3. 确定周线枢轴价（使用最近20周的最高价）
    recent_20w = weekly_df.tail(20)
    weekly_pivot = recent_20w['high'].max() if 'high' in recent_20w else weekly_info.get('ma40_weekly', 0)
    
    # 4. 检测触发信号
    signal = None
    
    # 先检测突破
    breakout_signal = detect_breakout_trigger(daily_df, weekly_pivot, config)
    if breakout_signal:
        signal = breakout_signal
    
    # 再检测回踩
    if not signal:
        pullback_signal = detect_pullback_trigger(daily_df, config)
        if pullback_signal:
            signal = pullback_signal
    
    if not signal:
        return None
    
    # 5. 计算入场价、止损价
    latest = daily_df.iloc[-1]
    entry_price = float(latest['close'])
    stop_loss, risk_pct = calculate_stop_loss(daily_df, entry_price, config)
    
    # 6. 计算支撑阻力
    sr = find_support_resistance(daily_df, lookback=20)
    
    # 7. 构建结果
    result = {
        'code': stock_code,
        'name': weekly_info.get('name', stock_code),
        'trigger_type': signal['trigger_type'],
        'entry_price': entry_price,
        'stop_loss': round(stop_loss, 2),
        'risk_pct': round(risk_pct * 100, 2),
        'volume_ratio': round(signal.get('volume_ratio', 0), 2),
        'rsi': round(signal.get('rsi', 0), 1),
        'signal_strength': signal['signal_strength'],
        'weekly_score': weekly_info.get('weekly_score', 0),
        'monthly_trend': weekly_info.get('monthly_trend', ''),
        'support': round(sr.get('support', 0), 2),
        'resistance': round(sr.get('resistance', 0), 2),
        'date': latest['date'],
    }
    
    # 添加特定触发类型的额外信息
    if signal['trigger_type'] == 'PULLBACK':
        result['support_ma'] = signal.get('support_ma', 0)
        result['drawdown'] = round(signal.get('drawdown', 0) * 100, 2)
    
    return result


def main() -> int:
    args = parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 确定数据目录和输出路径
    data_dir = Path(args.data_dir if args.data_dir else config['paths']['kline_data_dir'])
    output_dir = Path(config['paths']['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = args.output if args.output else output_dir / config['paths']['daily_signals_file']
    
    # 加载观察池
    watchlist_path = Path(args.watchlist)
    if not watchlist_path.exists():
        print(f"错误: 观察池文件不存在: {watchlist_path}")
        print("请先运行 weekly_scan.py 生成观察池")
        return 1
    
    watchlist_df = pd.read_csv(watchlist_path)
    
    print("=" * 80)
    print("日线触发信号扫描器")
    print("=" * 80)
    print(f"观察池文件: {watchlist_path}")
    print(f"观察池股票数: {len(watchlist_df)}")
    print(f"数据目录: {data_dir}")
    print(f"输出文件: {output_path}")
    print("=" * 80)
    
    # 处理观察池中的每只股票
    signals = []
    print("\n开始扫描触发信号...")
    
    for idx, row in tqdm(watchlist_df.iterrows(), total=len(watchlist_df), desc="扫描进度"):
        stock_code = row['code']
        
        try:
            signal = process_single_stock(stock_code, data_dir, row.to_dict(), config)
            if signal:
                signals.append(signal)
        except Exception as e:
            print(f"\n处理 {stock_code} 时出错: {e}")
            continue
    
    # 生成报告
    if not signals:
        print("\n今日未发现触发信号！")
        # 创建空文件
        pd.DataFrame(columns=['code', 'name', 'trigger_type', 'entry_price', 'stop_loss', 
                              'risk_pct', 'signal_strength']).to_csv(output_path, index=False, encoding='utf-8-sig')
        return 0
    
    # 转换为DataFrame
    signals_df = pd.DataFrame(signals)
    
    # 按信号强度和周线评分排序
    signals_df['composite_score'] = signals_df['signal_strength'] * 30 + signals_df['weekly_score'] * 0.7
    signals_df = signals_df.sort_values('composite_score', ascending=False)
    
    # 限制数量
    max_signals = config['output']['daily_signals']['max_signals']
    signals_df = signals_df.head(max_signals)
    
    # 保存结果
    output_cols = ['code', 'name', 'trigger_type', 'entry_price', 'stop_loss', 'risk_pct',
                   'volume_ratio', 'rsi', 'signal_strength', 'weekly_score', 'monthly_trend',
                   'support', 'resistance', 'date']
    
    # 确保所有列都存在
    for col in output_cols:
        if col not in signals_df.columns:
            signals_df[col] = ''
    
    signals_df[output_cols].to_csv(output_path, index=False, encoding='utf-8-sig')
    
    # 打印统计
    print("\n" + "=" * 80)
    print("扫描完成！")
    print("=" * 80)
    print(f"发现触发信号数量: {len(signals_df)}")
    print(f"\n触发类型分布:")
    print(signals_df['trigger_type'].value_counts())
    print(f"\n月线趋势分布:")
    print(signals_df['monthly_trend'].value_counts())
    print(f"\n风险统计:")
    print(f"  平均风险: {signals_df['risk_pct'].mean():.2f}%")
    print(f"  最大风险: {signals_df['risk_pct'].max():.2f}%")
    print(f"  最小风险: {signals_df['risk_pct'].min():.2f}%")
    print(f"\n结果已保存到: {output_path}")
    print("=" * 80)
    
    # 显示所有信号
    print("\n🎯 今日触发信号:")
    display_df = signals_df[['code', 'name', 'trigger_type', 'entry_price', 'stop_loss', 
                             'risk_pct', 'volume_ratio', 'signal_strength']].copy()
    display_df.columns = ['代码', '名称', '类型', '入场价', '止损价', '风险%', '量比', '强度']
    print(display_df.to_string(index=False))
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

