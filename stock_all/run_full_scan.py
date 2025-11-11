"""
完整筛选流程：规则粗筛 + ML精筛
两阶段策略：5000只 → 200只 → 50只

使用方法:
    python stock_all/run_full_scan.py --config stock_all/config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from ml_ranker import MLRanker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="完整筛选流程：规则粗筛 + ML精筛")
    parser.add_argument(
        "--config",
        default="stock_all/config.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="K线数据目录（覆盖配置文件）",
    )
    parser.add_argument(
        "--watchlist",
        default=None,
        help="观察池文件路径（如果已经运行了weekly_scan）",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="输出目录（覆盖配置文件）",
    )
    parser.add_argument(
        "--skip-rules",
        action="store_true",
        help="跳过规则筛选，直接使用已有的观察池",
    )
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def run_rule_screening(config: dict, data_dir: Path, output_dir: Path) -> Path:
    """
    运行规则筛选（阶段1）
    
    Returns:
        观察池文件路径
    """
    print("\n" + "=" * 80)
    print("【阶段 1/2】规则粗筛")
    print("=" * 80)
    print("使用月线大势判定 + 周线结构验证")
    print("目标：从5000只股票中筛选出200只候选股")
    print("-" * 80)
    
    # 这里调用weekly_scan的逻辑
    # 为了简化，我们假设用户已经运行了weekly_scan.py
    watchlist_path = output_dir / config['paths']['watchlist_file']
    
    if not watchlist_path.exists():
        print(f"\n❌ 错误：未找到观察池文件: {watchlist_path}")
        print("\n请先运行规则筛选：")
        print("  python stock_all/weekly_scan.py --config stock_all/config.yaml")
        print("\n或使用 --watchlist 参数指定观察池文件")
        return None
    
    # 读取观察池
    watchlist_df = pd.read_csv(watchlist_path)
    print(f"\n✅ 规则筛选完成")
    print(f"   候选股数量: {len(watchlist_df)} 只")
    print(f"   观察池文件: {watchlist_path}")
    
    return watchlist_path


def run_ml_ranking(config: dict, watchlist_path: Path, data_dir: Path, output_dir: Path) -> pd.DataFrame:
    """
    运行ML排序（阶段2）
    
    Returns:
        排序后的DataFrame
    """
    print("\n" + "=" * 80)
    print("【阶段 2/2】ML精筛与智能排序")
    print("=" * 80)
    print("使用30个核心特征 + Prophet预测 + 智能评分")
    print("目标：从200只候选股中选出50只最优股")
    print("-" * 80)
    
    # 加载观察池
    watchlist_df = pd.read_csv(watchlist_path)
    print(f"\n输入：{len(watchlist_df)} 只候选股")
    
    # 创建ML排序器
    ranker = MLRanker(config)
    
    # 执行排序
    ranked_df = ranker.rank_stocks(watchlist_df, data_dir)
    
    if ranked_df.empty:
        print("\n❌ ML排序失败：没有股票通过评分")
        return None
    
    print(f"\n✅ ML排序完成")
    print(f"   精选股票数量: {len(ranked_df)} 只")
    
    return ranked_df


def save_results(ranked_df: pd.DataFrame, output_dir: Path, config: dict):
    """保存结果"""
    output_file = output_dir / "ranked_stocks.csv"
    
    # 选择输出列
    output_cols = [
        'code', 'name', 'monthly_trend', 'weekly_score',
        'ml_score', 'prophet_forecast_return', 'prophet_trend',
        'prophet_confidence', 'current_price', 'ma40_weekly',
        'volume_ratio', 'date', 'key_features'
    ]
    
    # 确保所有列存在
    available_cols = [col for col in output_cols if col in ranked_df.columns]
    
    # 保存
    ranked_df[available_cols].to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"\n📁 结果已保存到: {output_file}")


def print_statistics(ranked_df: pd.DataFrame):
    """打印统计信息"""
    print("\n" + "=" * 80)
    print("📊 统计报告")
    print("=" * 80)
    
    # ML评分统计
    print(f"\n🎯 ML评分统计:")
    print(f"   平均分: {ranked_df['ml_score'].mean():.2f}")
    print(f"   最高分: {ranked_df['ml_score'].max():.2f}")
    print(f"   最低分: {ranked_df['ml_score'].min():.2f}")
    
    # Prophet预测统计
    if 'prophet_forecast_return' in ranked_df.columns:
        print(f"\n📈 Prophet预测统计:")
        print(f"   预测平均收益: {ranked_df['prophet_forecast_return'].mean():.2f}%")
        print(f"   预测看涨(>5%): {(ranked_df['prophet_forecast_return'] > 5).sum()} 只")
        print(f"   预测看平(±5%): {((ranked_df['prophet_forecast_return'] >= -5) & (ranked_df['prophet_forecast_return'] <= 5)).sum()} 只")
        print(f"   预测看跌(<-5%): {(ranked_df['prophet_forecast_return'] < -5).sum()} 只")
    
    # 月线状态分布
    if 'monthly_trend' in ranked_df.columns:
        print(f"\n📊 月线状态分布:")
        trend_counts = ranked_df['monthly_trend'].value_counts()
        for trend, count in trend_counts.items():
            print(f"   {trend}: {count} 只")


def print_top_stocks(ranked_df: pd.DataFrame, top_n: int = 10):
    """打印评分最高的股票"""
    print("\n" + "=" * 80)
    print(f"🏆 评分最高的前{top_n}只股票")
    print("=" * 80)
    
    # 选择显示列
    display_cols = ['code', 'name', 'ml_score', 'prophet_forecast_return', 
                    'prophet_trend', 'current_price', 'key_features']
    
    # 确保列存在
    available_cols = [col for col in display_cols if col in ranked_df.columns]
    
    display_df = ranked_df[available_cols].head(top_n).copy()
    
    # 重命名列（中文）
    col_mapping = {
        'code': '代码',
        'name': '名称',
        'ml_score': 'ML评分',
        'prophet_forecast_return': '预测收益%',
        'prophet_trend': 'Prophet趋势',
        'current_price': '当前价',
        'key_features': '关键特征'
    }
    
    display_df = display_df.rename(columns={k: v for k, v in col_mapping.items() if k in display_df.columns})
    
    # 格式化输出
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 30)
    
    print(display_df.to_string(index=False))
    print("=" * 80)


def main() -> int:
    args = parse_args()
    
    # 加载配置
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"错误：无法加载配置文件 {args.config}: {e}")
        return 1
    
    # 确定路径
    data_dir = Path(args.data_dir if args.data_dir else config['paths']['kline_data_dir'])
    output_dir = Path(args.output_dir if args.output_dir else config['paths']['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 打印标题
    print("\n" + "=" * 80)
    print("🚀 股票智能筛选系统 - 完整流程")
    print("=" * 80)
    print(f"📂 数据目录: {data_dir}")
    print(f"📁 输出目录: {output_dir}")
    print(f"⚙️  配置文件: {args.config}")
    
    # 检查数据目录
    if not data_dir.exists():
        print(f"\n❌ 错误：数据目录不存在: {data_dir}")
        print("\n请先获取K线数据：")
        print("  python stock_all/fetch_kline_history.py --output-dir ./kline_data")
        return 1
    
    try:
        # ===== 阶段1：规则筛选 =====
        if args.skip_rules and args.watchlist:
            watchlist_path = Path(args.watchlist)
            if not watchlist_path.exists():
                print(f"错误：观察池文件不存在: {watchlist_path}")
                return 1
            print(f"\n跳过规则筛选，使用已有观察池: {watchlist_path}")
        else:
            watchlist_path = run_rule_screening(config, data_dir, output_dir)
            if watchlist_path is None:
                return 1
        
        # ===== 阶段2：ML排序 =====
        if not config.get('ml_ranking', {}).get('enabled', True):
            print("\nML排序未启用，使用规则筛选结果")
            return 0
        
        ranked_df = run_ml_ranking(config, watchlist_path, data_dir, output_dir)
        
        if ranked_df is None or ranked_df.empty:
            print("\nML排序未产生结果")
            return 1
        
        # ===== 保存结果 =====
        save_results(ranked_df, output_dir, config)
        
        # ===== 打印统计 =====
        print_statistics(ranked_df)
        
        # ===== 打印Top股票 =====
        print_top_stocks(ranked_df, top_n=10)
        
        print("\n✅ 完整流程执行成功！")
        print(f"📁 查看结果: {output_dir / 'ranked_stocks.csv'}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
        return 1
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

