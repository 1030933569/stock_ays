"""
快速获取股票名称映射表
只需几秒钟，无需下载K线数据

使用方法:
    python stock_all/fetch_stock_names.py
"""

import baostock as bs
import pandas as pd
from pathlib import Path


def main():
    print("正在获取股票名称映射表...", flush=True)
    
    # 登录 baostock
    lg = bs.login()
    if lg.error_code != "0":
        print(f"登录失败: {lg.error_msg}")
        return 1
    
    try:
        # 获取股票列表
        rs = bs.query_all_stock(day="2024-11-01")
        
        if rs.error_code != "0":
            print(f"获取失败: {rs.error_msg}")
            return 1
        
        data_list = []
        while rs.next():
            row = rs.get_row_data()
            data_list.append(row)
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 只保留股票（排除指数等）
        df = df[df["code"].str.contains(r"^(?:sh\.6|sz\.0|sz\.3)", regex=True, na=False)]
        
        # 提取代码和名称
        result = df[['code', 'code_name']].copy()
        result.columns = ['code', 'name']
        # 去掉 sh./sz. 前缀
        result['code'] = result['code'].str.replace(r'^(sh|sz)\.', '', regex=True)
        
        # 保存到 kline_data 目录
        output_dir = Path(__file__).parent.parent / "kline_data"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "stock_names.csv"
        
        result.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"✅ 完成！共 {len(result)} 只股票")
        print(f"📁 已保存到: {output_file}")
        
    finally:
        bs.logout()
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

