"""
定时调度器 - 用于Render Background Worker部署
自动执行周线筛选和日线扫描任务
"""

import schedule
import time
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd, description):
    """运行命令并记录日志"""
    print("=" * 80)
    print(f"[{datetime.now()}] 开始执行: {description}")
    print("=" * 80)
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3600  # 1小时超时
        )
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
        
        if result.returncode == 0:
            print(f"[{datetime.now()}] ✅ {description} 执行成功")
        else:
            print(f"[{datetime.now()}] ❌ {description} 执行失败，返回码: {result.returncode}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"[{datetime.now()}] ⏰ {description} 执行超时")
        return False
    except Exception as e:
        print(f"[{datetime.now()}] ❌ {description} 执行异常: {e}")
        return False


def run_weekly_scan():
    """周线筛选 + ML排序"""
    cmd = "cd stock_all && python run_full_scan.py --config config.yaml"
    run_command(cmd, "周线筛选和ML排序")


def run_daily_scan():
    """日线信号扫描"""
    # 检查观察池是否存在
    watchlist_path = Path("output/watchlist.csv")
    if not watchlist_path.exists():
        print(f"[{datetime.now()}] ⚠️  观察池文件不存在，跳过日线扫描")
        print("提示: 请先运行周线筛选生成观察池")
        return False
    
    cmd = "cd stock_all && python daily_scan.py --config config.yaml --watchlist ../output/watchlist.csv"
    return run_command(cmd, "日线信号扫描")


def update_data():
    """更新K线数据（每周执行一次）"""
    cmd = "cd stock_all && python fetch_kline_history.py --output-dir ../kline_data --delay 0.05"
    run_command(cmd, "K线数据更新")


def setup_schedule():
    """配置定时任务"""
    print("\n" + "=" * 80)
    print("📅 配置定时任务")
    print("=" * 80)
    
    # 周线筛选：每周五 15:30（A股收盘后）
    schedule.every().friday.at("15:30").do(run_weekly_scan)
    print("✓ 周线筛选: 每周五 15:30")
    
    # 日线扫描：周一到周五 15:30
    schedule.every().monday.at("15:30").do(run_daily_scan)
    schedule.every().tuesday.at("15:30").do(run_daily_scan)
    schedule.every().wednesday.at("15:30").do(run_daily_scan)
    schedule.every().thursday.at("15:30").do(run_daily_scan)
    schedule.every().friday.at("15:35").do(run_daily_scan)  # 周五稍晚，等周线筛选完成
    print("✓ 日线扫描: 周一到周五 15:30")
    
    # 数据更新：每周日 20:00
    schedule.every().sunday.at("20:00").do(update_data)
    print("✓ 数据更新: 每周日 20:00")
    
    print("=" * 80)


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("🚀 股票筛选系统 - 定时调度器")
    print("=" * 80)
    print(f"启动时间: {datetime.now()}")
    print(f"工作目录: {Path.cwd()}")
    print("=" * 80)
    
    # 配置定时任务
    setup_schedule()
    
    print("\n⏰ 调度器已启动，等待执行任务...")
    print("提示: 按 Ctrl+C 停止\n")
    
    # 主循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
            
    except KeyboardInterrupt:
        print("\n\n用户中断，调度器已停止")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ 调度器异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # 检查必要的目录
    Path("output").mkdir(exist_ok=True)
    Path("kline_data").mkdir(exist_ok=True)
    
    # 启动调度器
    main()

