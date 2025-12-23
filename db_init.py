"""
数据库初始化脚本 - 创建K线数据表
添加重试机制，每个表单独创建
"""

import time
from db_config import get_connection


def create_table_with_retry(sql: str, table_name: str, max_retries: int = 3):
    """创建表（带重试机制）"""
    for attempt in range(max_retries):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            cursor.close()
            conn.close()
            print(f"✅ {table_name} 表创建成功")
            return True
        except Exception as e:
            print(f"⚠️ {table_name} 创建失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 等待2秒后重试
            else:
                print(f"❌ {table_name} 创建失败，已达最大重试次数")
                return False


def create_tables():
    """创建K线数据表"""
    print("🔧 开始创建数据库表...")
    
    # 日线表
    daily_sql = '''
        CREATE TABLE IF NOT EXISTS kline_daily (
            date DATE NOT NULL,
            code VARCHAR(10) NOT NULL,
            open DECIMAL(10,4),
            high DECIMAL(10,4),
            low DECIMAL(10,4),
            close DECIMAL(10,4),
            preclose DECIMAL(10,4),
            volume BIGINT,
            amount DECIMAL(20,4),
            adjustflag VARCHAR(2),
            turn DECIMAL(10,6),
            tradestatus VARCHAR(2),
            pctChg DECIMAL(10,6),
            isST VARCHAR(2),
            PRIMARY KEY (code, date)
        )
    '''
    create_table_with_retry(daily_sql, "kline_daily")
    
    time.sleep(1)  # 等待1秒
    
    # 周线表
    weekly_sql = '''
        CREATE TABLE IF NOT EXISTS kline_weekly (
            date DATE NOT NULL,
            code VARCHAR(10) NOT NULL,
            open DECIMAL(10,4),
            high DECIMAL(10,4),
            low DECIMAL(10,4),
            close DECIMAL(10,4),
            volume BIGINT,
            amount DECIMAL(20,4),
            adjustflag VARCHAR(2),
            turn DECIMAL(10,6),
            pctChg DECIMAL(10,6),
            PRIMARY KEY (code, date)
        )
    '''
    create_table_with_retry(weekly_sql, "kline_weekly")
    
    time.sleep(1)
    
    # 月线表
    monthly_sql = '''
        CREATE TABLE IF NOT EXISTS kline_monthly (
            date DATE NOT NULL,
            code VARCHAR(10) NOT NULL,
            open DECIMAL(10,4),
            high DECIMAL(10,4),
            low DECIMAL(10,4),
            close DECIMAL(10,4),
            volume BIGINT,
            amount DECIMAL(20,4),
            adjustflag VARCHAR(2),
            turn DECIMAL(10,6),
            pctChg DECIMAL(10,6),
            PRIMARY KEY (code, date)
        )
    '''
    create_table_with_retry(monthly_sql, "kline_monthly")
    
    print("\n🎉 表创建流程完成！")


def show_tables():
    """显示已创建的表"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print("\n📋 数据库中的表：")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"查询表失败: {e}")


if __name__ == '__main__':
    create_tables()
    show_tables()
