#!/bin/bash
# 日线信号扫描启动脚本

set -e

echo "========================================="
echo "开始日线信号扫描"
echo "时间: $(date)"
echo "========================================="

# 进入工作目录
cd stock_all

# 检查观察池文件是否存在
if [ ! -f "../output/watchlist.csv" ]; then
    echo "错误: 观察池文件不存在，先运行周线筛选"
    exit 1
fi

# 运行日线扫描
python daily_scan.py --config config.yaml --watchlist ../output/watchlist.csv

echo "========================================="
echo "日线扫描完成"
echo "时间: $(date)"
echo "========================================="

