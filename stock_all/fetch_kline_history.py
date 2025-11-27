"""
获取A股所有公司的K线历史数据
- 月线：10年
- 周线：5年
- 日线：1年

使用 baostock 库获取数据并保存到本地CSV文件

使用方法:
    python stock_all/fetch_kline_history.py --output-dir ./kline_data
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import baostock as bs
import pandas as pd
from tqdm import tqdm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="获取A股所有公司的K线历史数据（月线10年、周线5年、日线1年）"
    )
    parser.add_argument(
        "--output-dir",
        default="./kline_data",
        help="输出目录路径（默认: ./kline_data）",
    )
    parser.add_argument(
        "--stock-type",
        default="1",
        help="股票类型：1-股票，2-指数（默认: 1）",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="CSV文件编码（默认: utf-8-sig，Excel可直接打开）",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="每次请求之间的延迟秒数（默认: 0.1）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制获取的股票数量，用于测试（默认: None，获取所有）",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="跳过已下载的股票，断点续传（默认: True）",
    )
    return parser.parse_args()


def login() -> None:
    """登录 baostock"""
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"Baostock 登录失败: {lg.error_msg}")
    print("Baostock 登录成功", flush=True)


def logout() -> None:
    """登出 baostock"""
    bs.logout()
    print("Baostock 登出成功", flush=True)


def get_stock_list(stock_type: str = "1") -> pd.DataFrame:
    """
    获取所有A股股票列表
    
    Args:
        stock_type: 股票类型，1-股票，2-指数
        
    Returns:
        包含股票代码和名称的DataFrame
    """
    print("正在获取股票列表...", flush=True)
    # 使用一个固定的日期（最近的交易日）避免周末或节假日没有数据
    # 可以使用 2024-11-01 这样的日期
    query_date = "2024-11-01"  # 使用一个确定有数据的交易日
    rs = bs.query_all_stock(day=query_date)
    
    if rs.error_code != "0":
        raise RuntimeError(f"获取股票列表失败: {rs.error_msg}")
    
    data_list = []
    while rs.next():
        row = rs.get_row_data()
        data_list.append(row)
    
    df = pd.DataFrame(data_list, columns=rs.fields)
    
    # 筛选股票类型
    if stock_type == "1":
        # 只保留股票（sh.6xxxxx 或 sz.0xxxxx, sz.3xxxxx）
        # 使用 str.contains，(?:...) 表示非捕获组避免警告
        df = df[df["code"].str.contains(r"^(?:sh\.6|sz\.0|sz\.3)", regex=True, na=False)]
    
    print(f"共获取到 {len(df)} 只股票", flush=True)
    return df


def calculate_date_range(years: int) -> tuple[str, str]:
    """
    计算日期范围
    
    Args:
        years: 年数
        
    Returns:
        (start_date, end_date) 格式: YYYY-MM-DD
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=years * 365)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def fetch_kline_data(
    code: str,
    start_date: str,
    end_date: str,
    frequency: str = "d",
    adjustflag: str = "3",
    max_retries: int = 3
) -> Optional[pd.DataFrame]:
    """
    获取单只股票的K线数据（带重试机制）
    
    Args:
        code: 股票代码，如 sh.600000
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        frequency: 数据频率，d-日，w-周，m-月
        adjustflag: 复权类型，1-后复权，2-前复权，3-不复权
        max_retries: 最大重试次数
        
    Returns:
        K线数据DataFrame，失败返回None
    """
    # 根据频率选择不同的字段
    if frequency == "d":
        fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
    else:  # 周线和月线
        fields = "date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg"
    
    # 重试机制
    for attempt in range(max_retries):
        try:
            rs = bs.query_history_k_data_plus(
                code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag=adjustflag
            )
            
            if rs.error_code != "0":
                if attempt < max_retries - 1:
                    time.sleep(0.5)  # 等待后重试
                    continue
                else:
                    return None
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                row = rs.get_row_data()
                data_list.append(row)
            
            if not data_list:
                return None
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            return df
            
        except Exception as e:
            # 捕获编码错误、网络错误等异常
            if attempt < max_retries - 1:
                time.sleep(1)  # 等待更长时间后重试
                continue
            else:
                # 最后一次重试也失败，返回None
                return None
    
    return None


def save_kline_data(
    df: pd.DataFrame,
    output_path: Path,
    encoding: str = "utf-8-sig"
) -> None:
    """保存K线数据到CSV文件（覆盖模式）"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding=encoding)


def is_stock_downloaded(code: str, output_dir: Path) -> bool:
    """
    检查股票数据是否已完整下载
    
    Args:
        code: 股票代码（如 sh.600000）
        output_dir: 输出目录
        
    Returns:
        True表示已下载，False表示需要下载
    """
    # 清理股票代码
    clean_code = code.replace("sh.", "").replace("sz.", "")
    stock_dir = output_dir / clean_code
    
    # 检查3个文件是否都存在
    required_files = [
        stock_dir / f"{clean_code}_daily_1y.csv",
        stock_dir / f"{clean_code}_weekly_5y.csv",
        stock_dir / f"{clean_code}_monthly_10y.csv"
    ]
    
    for file_path in required_files:
        if not file_path.exists():
            return False
        # 简单检查文件大小
        try:
            if file_path.stat().st_size < 100:
                return False
        except:
            return False
    
    return True


def process_stock(
    code: str,
    stock_name: str,
    output_dir: Path,
    encoding: str,
    delay: float
) -> dict:
    """
    处理单只股票，获取其所有K线数据（完整下载模式）
    
    Returns:
        统计信息字典
    """
    stats = {"code": code, "name": stock_name, "daily": 0, "weekly": 0, "monthly": 0, "success": True}
    
    try:
        # 清理股票代码，用于文件名（去掉 sh. 或 sz. 前缀）
        clean_code = code.replace("sh.", "").replace("sz.", "")
        
        # 创建股票专属目录
        stock_dir = output_dir / clean_code
        
        # 1. 获取日线数据（1年）
        start_date, end_date = calculate_date_range(1)
        daily_df = fetch_kline_data(code, start_date, end_date, frequency="d", max_retries=3)
        if daily_df is not None and not daily_df.empty:
            save_kline_data(daily_df, stock_dir / f"{clean_code}_daily_1y.csv", encoding)
            stats["daily"] = len(daily_df)
        time.sleep(delay)
        
        # 2. 获取周线数据（5年）
        start_date, end_date = calculate_date_range(5)
        weekly_df = fetch_kline_data(code, start_date, end_date, frequency="w", max_retries=3)
        if weekly_df is not None and not weekly_df.empty:
            save_kline_data(weekly_df, stock_dir / f"{clean_code}_weekly_5y.csv", encoding)
            stats["weekly"] = len(weekly_df)
        time.sleep(delay)
        
        # 3. 获取月线数据（10年）
        start_date, end_date = calculate_date_range(10)
        monthly_df = fetch_kline_data(code, start_date, end_date, frequency="m", max_retries=3)
        if monthly_df is not None and not monthly_df.empty:
            save_kline_data(monthly_df, stock_dir / f"{clean_code}_monthly_10y.csv", encoding)
            stats["monthly"] = len(monthly_df)
        time.sleep(delay)
        
    except Exception as e:
        # 捕获任何异常，标记为失败但不中断整体流程
        stats["success"] = False
    
    return stats


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60, flush=True)
    print("A股K线历史数据获取工具（增量更新版）", flush=True)
    print("=" * 60, flush=True)
    print(f"输出目录: {output_dir}", flush=True)
    print(f"数据范围: 月线10年、周线5年、日线1年", flush=True)
    print(f"请求延迟: {args.delay}秒", flush=True)
    print(f"断点续传: {'开启' if args.skip_existing else '关闭'}", flush=True)
    print("=" * 60, flush=True)
    
    try:
        # 登录
        login()
        
        # 获取股票列表
        stock_list = get_stock_list(args.stock_type)
        
        # 如果设置了limit，只处理前N只股票
        if args.limit:
            stock_list = stock_list.head(args.limit)
            print(f"测试模式: 仅处理前 {args.limit} 只股票", flush=True)
        
        # 筛选需要下载的股票
        stocks_to_download = []
        skipped_count = 0
        
        if args.skip_existing:
            # 跳过模式：只处理缺失的股票
            print("\n检查已下载的股票...", flush=True)
            for idx, row in stock_list.iterrows():
                code = row["code"]
                if is_stock_downloaded(code, output_dir):
                    skipped_count += 1
                else:
                    stocks_to_download.append(row)
            
            print(f"已下载: {skipped_count} 只", flush=True)
            print(f"需要下载: {len(stocks_to_download)} 只", flush=True)
        else:
            stocks_to_download = [row for idx, row in stock_list.iterrows()]
        
        if not stocks_to_download:
            print("\n所有股票数据已存在，无需下载！", flush=True)
            return 0
        
        # 串行处理（baostock不支持并发）
        all_stats = []
        failed_stocks = []
        print(f"\n开始下载K线数据（断点续传模式）...", flush=True)
        
        for row in tqdm(stocks_to_download, desc="下载进度"):
            code = row["code"]
            stock_name = row.get("code_name", "")
            
            try:
                stats = process_stock(code, stock_name, output_dir, args.encoding, args.delay)
                all_stats.append(stats)
                
                # 记录失败的股票
                if not stats.get("success", True):
                    failed_stocks.append(f"{code}({stock_name})")
            except Exception as e:
                failed_stocks.append(f"{code}({stock_name}): {str(e)[:50]}")
                continue
        
        # 保存统计信息
        stats_df = pd.DataFrame(all_stats)
        stats_path = output_dir / "fetch_statistics.csv"
        stats_df.to_csv(stats_path, index=False, encoding=args.encoding)
        
        # 保存股票名称映射表（供 API 使用）
        stock_names_df = pd.DataFrame(stock_list)[['code', 'code_name']]
        stock_names_df.columns = ['code', 'name']
        # 提取纯代码（去掉 sh./sz. 前缀）
        stock_names_df['code'] = stock_names_df['code'].str.replace(r'^(sh|sz)\.', '', regex=True)
        stock_names_path = output_dir / "stock_names.csv"
        stock_names_df.to_csv(stock_names_path, index=False, encoding=args.encoding)
        print(f"股票名称映射已保存到: {stock_names_path}", flush=True)
        
        # 打印汇总信息
        print("\n" + "=" * 60, flush=True)
        print("数据获取完成！", flush=True)
        print("=" * 60, flush=True)
        if args.skip_existing:
            print(f"跳过已下载: {skipped_count} 只", flush=True)
        print(f"本次下载: {len(all_stats)} 只", flush=True)
        if failed_stocks:
            print(f"失败: {len(failed_stocks)} 只", flush=True)
        print(f"总股票数: {len(stock_list)} 只", flush=True)
        print(f"日线数据总条数: {stats_df['daily'].sum()}", flush=True)
        print(f"周线数据总条数: {stats_df['weekly'].sum()}", flush=True)
        print(f"月线数据总条数: {stats_df['monthly'].sum()}", flush=True)
        print(f"统计信息已保存到: {stats_path}", flush=True)
        
        # 如果有失败的股票，保存到文件
        if failed_stocks:
            failed_path = output_dir / "failed_stocks.txt"
            with open(failed_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(failed_stocks))
            print(f"失败股票列表已保存到: {failed_path}", flush=True)
        
        print("=" * 60, flush=True)
        
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    finally:
        logout()
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

