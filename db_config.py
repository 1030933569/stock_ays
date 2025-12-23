"""
数据库配置文件
从环境变量读取配置，支持本地 .env 文件
支持 TiDB Cloud SSL 连接
"""

import os
import ssl
from pathlib import Path

# 尝试加载 .env 文件（本地开发用）
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


# 数据库配置（从环境变量读取）
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'stock_db'),
    'charset': 'utf8mb4'
}

# 是否启用 SSL（TiDB Cloud 需要）
USE_SSL = os.getenv('DB_SSL', 'true').lower() == 'true'


def get_connection():
    """获取数据库连接"""
    import pymysql
    
    config = DB_CONFIG.copy()
    
    # TiDB Cloud Serverless 需要 SSL 连接
    if USE_SSL:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        config['ssl'] = ssl_context
    
    return pymysql.connect(**config)


def test_connection():
    """测试数据库连接"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        print(f"✅ 数据库连接成功！")
        print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"   Database: {DB_CONFIG['database']}")
        print(f"   Version: {version}")
        print(f"   SSL: {'启用' if USE_SSL else '未启用'}")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


if __name__ == '__main__':
    test_connection()
