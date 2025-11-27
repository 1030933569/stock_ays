"""
周线级别股票筛选器
- 月线大势判定（上升趋势/底部筑底/下跌趋势）
- 周线结构验证（均线/动能/形态）
- 生成重点观察股票池

使用方法:
    python stock_all/weekly_scan.py --config stock_all/config.yaml
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
    analyze_volume_pattern,
    calculate_all_indicators,
    calculate_ma_slope,
    check_ma_alignment,
    detect_macd_golden_cross,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="周线级别股票筛选器")
    parser.add_argument(
        "--config",
        default="stock_all/config.yaml",
        help="配置文件路径",
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
        print(f"加载 {file_path} 失败: {e}")
        return None


def pre_filter_stock(stock_code: str, daily_df: pd.DataFrame, config: dict) -> tuple[bool, str]:
    """
    基础预过滤
    
    Returns:
        (是否通过, 失败原因)
    """
    params = config['pre_filter']
    
    # 检查ST股票
    if params['exclude_st'] and 'isST' in daily_df.columns:
        if daily_df['isST'].iloc[-1] == '1':
            return False, "ST股票"
    
    # 检查数据完整性
    if len(daily_df) < 60:  # 至少60个交易日
        return False, "数据不足"
    
    # 检查停牌（最近5日）
    recent_5d = daily_df.tail(5)
    if 'tradestatus' in recent_5d.columns:
        suspend_days = (recent_5d['tradestatus'] == '0').sum()
        if suspend_days > params['max_suspend_days_5d']:
            return False, f"停牌天数过多({suspend_days})"
    
    # 检查20日均成交额
    if 'amount' in daily_df.columns:
        daily_df['amount'] = pd.to_numeric(daily_df['amount'], errors='coerce')
        avg_amount_20d = daily_df['amount'].tail(20).mean()
        if avg_amount_20d < params['min_avg_amount_20d']:
            return False, f"成交额不足({avg_amount_20d/1e8:.2f}亿)"
    
    return True, ""


def judge_monthly_trend(monthly_df: pd.DataFrame, config: dict) -> str:
    """
    判定月线大势
    
    Returns:
        "UPTREND" | "BASE_BUILDING" | "DOWNTREND"
    """
    if monthly_df is None or len(monthly_df) < 12:
        return "DOWNTREND"
    
    # 计算指标
    monthly_df = calculate_all_indicators(monthly_df, freq='monthly')
    
    params_up = config['monthly']['uptrend']
    params_base = config['monthly']['base_building']
    
    latest = monthly_df.iloc[-1]
    
    # ===== 上升趋势判定 =====
    uptrend_score = 0
    uptrend_checks = 0
    
    # 1. 收盘价高于10月均线
    if params_up['close_above_ma10'] and 'MA10' in monthly_df.columns:
        if not pd.isna(latest['MA10']) and latest['close'] > latest['MA10']:
            uptrend_score += 1
        uptrend_checks += 1
    
    # 2. MA10斜率向上
    if 'MA10_slope' in monthly_df.columns:
        if not pd.isna(latest['MA10_slope']) and latest['MA10_slope'] >= params_up['ma10_slope_min']:
            uptrend_score += 1
        uptrend_checks += 1
    
    # 3. 均线多头排列
    if params_up['ma_alignment_check']:
        ma_aligned = check_ma_alignment(monthly_df.tail(1), ['MA5', 'MA10', 'MA20'], ascending=True)
        if ma_aligned.iloc[0]:
            uptrend_score += 1
        uptrend_checks += 1
    
    # 4. 6个月涨幅
    if len(monthly_df) >= 6:
        gain_6m = (latest['close'] - monthly_df.iloc[-7]['close']) / monthly_df.iloc[-7]['close']
        if gain_6m >= params_up['gain_6m_min']:
            uptrend_score += 1
        uptrend_checks += 1
    
    # 如果上升趋势得分>=75%，判定为上升趋势
    if uptrend_checks > 0 and uptrend_score / uptrend_checks >= 0.75:
        return "UPTREND"
    
    # ===== 底部筑底判定 =====
    if len(monthly_df) >= 24:
        base_score = 0
        base_checks = 0
        
        # 1. 24个月内有过深度回调
        recent_24m = monthly_df.tail(24)
        max_price = recent_24m['close'].max()
        min_price = recent_24m['close'].min()
        drawdown = (max_price - min_price) / max_price
        
        if drawdown >= params_base['max_drawdown_24m']:
            base_score += 1
        base_checks += 1
        
        # 2. 横盘4-8个月且波动收敛
        for lookback in range(params_base['consolidation_months_min'], 
                             params_base['consolidation_months_max'] + 1):
            if len(monthly_df) >= lookback:
                consolidation_period = monthly_df.tail(lookback)
                volatility = consolidation_period['close'].std() / consolidation_period['close'].mean()
                
                if volatility < params_base['volatility_threshold']:
                    base_score += 1
                    break
        base_checks += 1
        
        # 3. MA10斜率接近0（走平）
        if 'MA10_slope' in monthly_df.columns and not pd.isna(latest['MA10_slope']):
            if params_base['ma10_slope_min'] <= latest['MA10_slope'] <= params_base['ma10_slope_max']:
                base_score += 1
            base_checks += 1
        
        # 4. 量能配合（上涨月量能>下跌月量能）
        if params_base['volume_cooperation']:
            volume_analysis = analyze_volume_pattern(monthly_df.tail(6), lookback=6)
            if volume_analysis['volume_cooperation']:
                base_score += 1
            base_checks += 1
        
        # 如果筑底得分>=75%，判定为底部筑底
        if base_checks > 0 and base_score / base_checks >= 0.75:
            return "BASE_BUILDING"
    
    # 其他情况判定为下跌趋势
    return "DOWNTREND"


def check_weekly_structure(weekly_df: pd.DataFrame, config: dict) -> dict:
    """
    检查周线结构
    
    Returns:
        {
            "passed": bool,
            "score": int (0-100),
            "details": dict
        }
    """
    if weekly_df is None or len(weekly_df) < 40:
        return {"passed": False, "score": 0, "details": {}}
    
    # 计算指标
    weekly_df = calculate_all_indicators(weekly_df, freq='weekly')
    
    params = config['weekly']['mandatory']
    latest = weekly_df.iloc[-1]
    
    result = {
        "passed": True,
        "score": 0,
        "details": {}
    }
    
    # ===== 必要条件检查 =====
    mandatory_score = 0
    mandatory_total = 0
    
    # 1. 收盘价高于40周均线
    if params['close_above_ma40'] and 'MA40' in weekly_df.columns:
        if pd.isna(latest['MA40']) or latest['close'] <= latest['MA40']:
            result['passed'] = False
            result['details']['ma40_check'] = False
        else:
            mandatory_score += 20
            result['details']['ma40_check'] = True
        mandatory_total += 20
    
    # 2. MA40斜率>=0
    if 'MA40_slope' in weekly_df.columns:
        if pd.isna(latest['MA40_slope']) or latest['MA40_slope'] < params['ma40_slope_min']:
            result['passed'] = False
            result['details']['ma40_slope_check'] = False
        else:
            mandatory_score += 15
            result['details']['ma40_slope_check'] = True
        mandatory_total += 15
    
    # 3. 收盘价高于10周均线
    if params['close_above_ma10'] and 'MA10' in weekly_df.columns:
        if pd.isna(latest['MA10']) or latest['close'] <= latest['MA10']:
            result['passed'] = False
            result['details']['ma10_check'] = False
        else:
            mandatory_score += 15
            result['details']['ma10_check'] = True
        mandatory_total += 15
    
    # 4. MACD正值或金叉
    if params['macd_positive_or_golden']:
        macd_ok = False
        if 'MACD_hist' in weekly_df.columns and not pd.isna(latest['MACD_hist']):
            if latest['MACD_hist'] > 0:
                macd_ok = True
            elif detect_macd_golden_cross(weekly_df, lookback=params['macd_lookback']):
                macd_ok = True
        
        if not macd_ok:
            result['passed'] = False
            result['details']['macd_check'] = False
        else:
            mandatory_score += 20
            result['details']['macd_check'] = True
        mandatory_total += 20
    
    # 5. 量能配合（上涨周>下跌周）
    volume_analysis = analyze_volume_pattern(
        weekly_df.tail(params['volume_lookback']), 
        lookback=params['volume_lookback']
    )
    
    if volume_analysis['volume_ratio'] < params['volume_ratio_min']:
        result['passed'] = False
        result['details']['volume_check'] = False
    else:
        mandatory_score += 30
        result['details']['volume_check'] = True
    mandatory_total += 30
    
    result['details']['volume_ratio'] = volume_analysis['volume_ratio']
    
    # 如果不通过必要条件，直接返回
    if not result['passed']:
        result['score'] = 0
        return result
    
    # 通过了必要条件，基础分就是mandatory_score
    result['score'] = mandatory_score
    
    # ===== 额外加分项（增加区分度） =====
    bonus_score = 0
    
    # 1. MA40斜率加分（最多10分）
    if 'MA40_slope' in weekly_df.columns and not pd.isna(latest['MA40_slope']):
        if latest['MA40_slope'] > 0.02:
            bonus_score += 10  # 强劲上升
        elif latest['MA40_slope'] > 0.01:
            bonus_score += 5   # 温和上升
    
    # 2. MACD强度加分（最多10分）
    if 'MACD_hist' in weekly_df.columns and not pd.isna(latest['MACD_hist']):
        if latest['MACD_hist'] > latest['close'] * 0.02:
            bonus_score += 10  # MACD柱状很强
        elif latest['MACD_hist'] > latest['close'] * 0.01:
            bonus_score += 5
    
    # 3. 量能强度加分（最多10分）
    if volume_analysis['volume_ratio'] > 1.5:
        bonus_score += 10  # 上涨周量能很强
    elif volume_analysis['volume_ratio'] > 1.3:
        bonus_score += 5
    
    # 4. 价格位置加分（最多10分）
    if 'MA10' in weekly_df.columns and not pd.isna(latest['MA10']):
        price_above_ma10 = (latest['close'] - latest['MA10']) / latest['MA10']
        if 0.02 < price_above_ma10 < 0.10:  # 刚站稳MA10，未涨太多
            bonus_score += 10
        elif 0.10 <= price_above_ma10 < 0.20:
            bonus_score += 5
    
    # 5. RSI适中加分（最多5分）
    if 'RSI' in weekly_df.columns and not pd.isna(latest['RSI']):
        if 50 < latest['RSI'] < 70:  # RSI在健康区间
            bonus_score += 5
    
    # 6. 连续放量加分（最多15分）
    consecutive_vol_config = config['weekly']['mandatory'].get('consecutive_volume', {})
    if consecutive_vol_config.get('enabled', False) and len(weekly_df) >= 8:
        min_weeks = consecutive_vol_config.get('min_weeks', 2)
        vol_increase_ratio = consecutive_vol_config.get('volume_increase_ratio', 1.2)
        max_bonus = consecutive_vol_config.get('max_bonus', 15)
        
        # 计算连续放量周数
        recent_weeks = weekly_df.tail(8)
        avg_volume_4w = recent_weeks.head(4)['volume'].mean()  # 前4周均量作为基准
        
        consecutive_count = 0
        for i in range(4, len(recent_weeks)):  # 检查最近4周
            week_volume = recent_weeks.iloc[i]['volume']
            if week_volume > avg_volume_4w * vol_increase_ratio:
                consecutive_count += 1
            else:
                consecutive_count = 0  # 中断则重置
        
        # 根据连续放量周数加分
        if consecutive_count >= min_weeks:
            # 连续2周+5分，3周+10分，4周+15分
            vol_bonus = min((consecutive_count - min_weeks + 1) * 5, max_bonus)
            bonus_score += vol_bonus
            result['details']['consecutive_volume_weeks'] = consecutive_count
    
    # 更新总分（基础分+加分，最多160分，后面会归一化）
    result['score'] = mandatory_score + bonus_score
    
    # 归一化到0-100（可选，保持兼容）
    # result['score'] = min(result['score'], 100)
    
    return result


def process_single_stock(stock_code: str, data_dir: Path, config: dict) -> Optional[dict]:
    """
    处理单只股票
    
    Returns:
        股票分析结果字典或None
    """
    # 1. 加载数据
    daily_df = load_kline_data(stock_code, data_dir, 'daily')
    weekly_df = load_kline_data(stock_code, data_dir, 'weekly')
    monthly_df = load_kline_data(stock_code, data_dir, 'monthly')
    
    if daily_df is None or weekly_df is None or monthly_df is None:
        return None
    
    # 2. 预过滤
    passed, reason = pre_filter_stock(stock_code, daily_df, config)
    if not passed:
        return None
    
    # 3. 月线大势判定
    monthly_trend = judge_monthly_trend(monthly_df, config)
    if monthly_trend == "DOWNTREND":
        return None
    
    # 4. 周线结构验证
    weekly_result = check_weekly_structure(weekly_df, config)
    if not weekly_result['passed']:
        return None
    
    # 5. 获取最新价格信息
    latest_daily = daily_df.iloc[-1]
    latest_weekly = weekly_df.iloc[-1]
    
    # 6. 构建结果
    result = {
        'code': stock_code,
        'name': latest_daily.get('code', stock_code),
        'monthly_trend': monthly_trend,
        'weekly_score': weekly_result['score'],
        'current_price': float(latest_daily['close']),
        'ma40_weekly': float(latest_weekly.get('MA40', 0)) if 'MA40' in latest_weekly else 0,
        'volume_ratio': weekly_result['details'].get('volume_ratio', 0),
        'date': latest_daily['date'],
        'details': weekly_result['details']
    }
    
    return result


def main() -> int:
    args = parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 确定数据目录和输出路径
    data_dir = Path(args.data_dir if args.data_dir else config['paths']['kline_data_dir'])
    output_dir = Path(config['paths']['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = args.output if args.output else output_dir / config['paths']['watchlist_file']
    
    print("=" * 80)
    print("周线级别股票筛选器")
    print("=" * 80)
    print(f"数据目录: {data_dir}")
    print(f"输出文件: {output_path}")
    print(f"配置文件: {args.config}")
    print("=" * 80)
    
    # 获取所有股票代码
    if not data_dir.exists():
        print(f"错误: 数据目录不存在: {data_dir}")
        return 1
    
    stock_dirs = [d for d in data_dir.iterdir() if d.is_dir()]
    print(f"共找到 {len(stock_dirs)} 只股票数据")
    
    # 处理每只股票
    results = []
    print("\n开始筛选...")
    
    for stock_dir in tqdm(stock_dirs, desc="筛选进度"):
        stock_code = stock_dir.name
        
        try:
            result = process_single_stock(stock_code, data_dir, config)
            if result:
                results.append(result)
        except Exception as e:
            print(f"\n处理 {stock_code} 时出错: {e}")
            continue
    
    # 生成报告
    if not results:
        print("\n未找到符合条件的股票！")
        return 0
    
    # 转换为DataFrame
    results_df = pd.DataFrame(results)
    
    # 按优先级排序
    prefer_base = config.get('output', {}).get('watchlist', {}).get('prefer_base_building', False)
    
    if prefer_base:
        # 优先底部筑底：BASE_BUILDING排前面，同类型按评分排序
        results_df['sort_priority'] = results_df['monthly_trend'].map({
            'BASE_BUILDING': 1,  # 筑底股票优先级最高
            'UPTREND': 2         # 上升趋势其次
        })
        results_df = results_df.sort_values(['sort_priority', 'weekly_score'], ascending=[True, False])
    else:
        # 默认：只按周线评分排序
        results_df = results_df.sort_values('weekly_score', ascending=False)
    
    # 限制数量
    max_stocks = config['output']['watchlist']['max_stocks']
    results_df = results_df.head(max_stocks)
    
    # 保存结果
    output_cols = ['code', 'name', 'monthly_trend', 'weekly_score', 
                   'current_price', 'ma40_weekly', 'volume_ratio', 'date']
    results_df[output_cols].to_csv(output_path, index=False, encoding='utf-8-sig')
    
    # 打印统计
    print("\n" + "=" * 80)
    print("筛选完成！")
    print("=" * 80)
    print(f"符合条件的股票数量: {len(results_df)}")
    print(f"\n月线状态分布:")
    print(results_df['monthly_trend'].value_counts())
    print(f"\n周线评分统计:")
    print(f"  平均分: {results_df['weekly_score'].mean():.2f}")
    print(f"  最高分: {results_df['weekly_score'].max():.0f}")
    print(f"  最低分: {results_df['weekly_score'].min():.0f}")
    print(f"\n结果已保存到: {output_path}")
    print("=" * 80)
    
    # 显示前10只股票
    print("\n🔥 评分最高的前10只股票:")
    print(results_df[output_cols].head(10).to_string(index=False))
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

