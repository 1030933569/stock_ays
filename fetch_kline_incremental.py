"""
增量获取K线数据脚本
- 日线：只获取最后日期到今天的新数据
- 周线：同一周则覆盖更新，否则追加
- 月线：同一月则覆盖更新，否则追加
"""

import time
from datetime import datetime, timedelta
from typing import Optional, Tuple

import baostock as bs
import pandas as pd
from tqdm import tqdm

from db_config import get_connection


def login_baostock():
    """登录 baostock"""
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"Baostock 登录失败: {lg.error_msg}")
    print("✅ Baostock 登录成功")


def logout_baostock():
    """登出 baostock"""
    bs.logout()
    print("✅ Baostock 登出成功")


def get_stock_list() -> pd.DataFrame:
    """获取所有A股股票列表"""
    print("📋 获取股票列表...")
    query_date = datetime.today().strftime("%Y-%m-%d")
    rs = bs.query_all_stock(day=query_date)
    
    if rs.error_code != "0":
        # 如果今天没数据，往前找
        for i in range(1, 10):
            query_date = (datetime.today() - timedelta(days=i)).strftime("%Y-%m-%d")
            rs = bs.query_all_stock(day=query_date)
            if rs.error_code == "0":
                break
    
    data_list = []
    while rs.next():
        data_list.append(rs.get_row_data())
    
    df = pd.DataFrame(data_list, columns=rs.fields)
    # 只保留股票（sh.6xxxxx 或 sz.0xxxxx, sz.3xxxxx）
    df = df[df["code"].str.contains(r"^(?:sh\.6|sz\.0|sz\.3)", regex=True, na=False)]
    
    print(f"✅ 共获取 {len(df)} 只股票")
    return df


def get_last_date(table: str, code: str) -> Optional[str]:
    """获取某只股票在数据库中的最后日期"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT MAX(date) FROM {table} WHERE code = %s", (code,))
    result = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    if result:
        return result.strftime("%Y-%m-%d")
    return None


def is_same_week(date1: str, date2: str) -> bool:
    """判断两个日期是否在同一周"""
    d1 = datetime.strptime(date1, "%Y-%m-%d")
    d2 = datetime.strptime(date2, "%Y-%m-%d")
    # 获取周一日期
    week1 = d1 - timedelta(days=d1.weekday())
    week2 = d2 - timedelta(days=d2.weekday())
    return week1 == week2


def is_same_month(date1: str, date2: str) -> bool:
    """判断两个日期是否在同一月"""
    d1 = datetime.strptime(date1, "%Y-%m-%d")
    d2 = datetime.strptime(date2, "%Y-%m-%d")
    return d1.year == d2.year and d1.month == d2.month


def get_week_start(date_str: str) -> str:
    """获取某日期所在周的周一"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("%Y-%m-%d")


def get_month_start(date_str: str) -> str:
    """获取某日期所在月的第一天"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.replace(day=1).strftime("%Y-%m-%d")


def fetch_kline(code: str, start_date: str, end_date: str, frequency: str) -> Optional[pd.DataFrame]:
    """获取K线数据"""
    if frequency == "d":
        fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
    else:
        fields = "date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg"
    
    rs = bs.query_history_k_data_plus(
        code, fields,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        adjustflag="3"
    )
    
    if rs.error_code != "0":
        return None
    
    data_list = []
    while rs.next():
        data_list.append(rs.get_row_data())
    
    if not data_list:
        return None
    
    return pd.DataFrame(data_list, columns=rs.fields)


def update_daily(code: str) -> int:
    """增量更新日线数据"""
    today = datetime.today().strftime("%Y-%m-%d")
    last_date = get_last_date("kline_daily", code)
    
    if last_date:
        # 从最后日期开始获取（包含最后一天，用于更新）
        start_date = last_date
    else:
        # 新股票，获取1年数据
        start_date = (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d")
    
    df = fetch_kline(code, start_date, today, "d")
    if df is None or df.empty:
        return 0
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for _, row in df.iterrows():
        cursor.execute('''
            REPLACE INTO kline_daily 
            (date, code, open, high, low, close, preclose, volume, amount, adjustflag, turn, tradestatus, pctChg, isST)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            row['date'], row['code'], row['open'], row['high'], row['low'], row['close'],
            row.get('preclose'), row['volume'], row['amount'], row.get('adjustflag'),
            row.get('turn'), row.get('tradestatus'), row.get('pctChg'), row.get('isST')
        ))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return len(df)


def update_weekly(code: str) -> int:
    """增量更新周线数据"""
    today = datetime.today().strftime("%Y-%m-%d")
    last_date = get_last_date("kline_weekly", code)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if last_date:
        if is_same_week(last_date, today):
            # 同一周，删除本周数据，重新获取
            week_start = get_week_start(today)
            cursor.execute("DELETE FROM kline_weekly WHERE code = %s AND date >= %s", (code, week_start))
            start_date = week_start
        else:
            # 新的一周，从上次日期开始
            start_date = last_date
    else:
        # 新股票，获取5年数据
        start_date = (datetime.today() - timedelta(days=365*5)).strftime("%Y-%m-%d")
    
    df = fetch_kline(code, start_date, today, "w")
    if df is None or df.empty:
        conn.commit()
        cursor.close()
        conn.close()
        return 0
    
    for _, row in df.iterrows():
        cursor.execute('''
            REPLACE INTO kline_weekly 
            (date, code, open, high, low, close, volume, amount, adjustflag, turn, pctChg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            row['date'], row['code'], row['open'], row['high'], row['low'], row['close'],
            row['volume'], row['amount'], row.get('adjustflag'), row.get('turn'), row.get('pctChg')
        ))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return len(df)


def update_monthly(code: str) -> int:
    """增量更新月线数据"""
    today = datetime.today().strftime("%Y-%m-%d")
    last_date = get_last_date("kline_monthly", code)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if last_date:
        if is_same_month(last_date, today):
            # 同一月，删除本月数据，重新获取
            month_start = get_month_start(today)
            cursor.execute("DELETE FROM kline_monthly WHERE code = %s AND date >= %s", (code, month_start))
            start_date = month_start
        else:
            # 新的一月，从上次日期开始
            start_date = last_date
    else:
        # 新股票，获取10年数据
        start_date = (datetime.today() - timedelta(days=365*10)).strftime("%Y-%m-%d")
    
    df = fetch_kline(code, start_date, today, "m")
    if df is None or df.empty:
        conn.commit()
        cursor.close()
        conn.close()
        return 0
    
    for _, row in df.iterrows():
        cursor.execute('''
            REPLACE INTO kline_monthly 
            (date, code, open, high, low, close, volume, amount, adjustflag, turn, pctChg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            row['date'], row['code'], row['open'], row['high'], row['low'], row['close'],
            row['volume'], row['amount'], row.get('adjustflag'), row.get('turn'), row.get('pctChg')
        ))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return len(df)


def main():
    print("=" * 60)
    print("K线数据增量更新")
    print("=" * 60)
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        login_baostock()
        stock_list = get_stock_list()
        
        daily_total = 0
        weekly_total = 0
        monthly_total = 0
        
        for _, row in tqdm(stock_list.iterrows(), total=len(stock_list), desc="更新进度"):
            code = row['code']
            
            try:
                # 更新日线
                daily_count = update_daily(code)
                daily_total += daily_count
                
                # 更新周线
                weekly_count = update_weekly(code)
                weekly_total += weekly_count
                
                # 更新月线
                monthly_count = update_monthly(code)
                monthly_total += monthly_count
                
                # 避免请求过快
                time.sleep(0.05)
                
            except Exception as e:
                print(f"\n⚠️ {code} 更新失败: {e}")
                continue
        
        print("\n" + "=" * 60)
        print("📊 更新统计：")
        print(f"  日线: {daily_total:,} 条")
        print(f"  周线: {weekly_total:,} 条")
        print(f"  月线: {monthly_total:,} 条")
        print("=" * 60)
        print("🎉 增量更新完成！")
        
    finally:
        logout_baostock()


if __name__ == '__main__':
    main()

