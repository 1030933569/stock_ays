# 股票筛选系统使用说明

## 🎯 核心功能

**两阶段筛选策略：**
```
5000只A股 → [规则筛选] → 200只候选股 → [ML精筛] → 50只精选股
```

---

## 📦 安装依赖

```bash
pip install pandas numpy scipy pyyaml tqdm baostock
pip install prophet lightgbm  # ML功能需要
```

---

## 🚀 使用流程

### **1. 获取K线数据（首次）**
```bash
python stock_all/fetch_kline_history.py --output-dir ./kline_data --delay 0.05
```

### **2. 规则筛选（每周）**
```bash
python stock_all/weekly_scan.py --config stock_all/config.yaml
# 输出: output/watchlist.csv (200只候选股)
```

### **3. ML精筛（每周）**
```bash
python stock_all/run_full_scan.py --config stock_all/config.yaml
# 输出: output/ranked_stocks.csv (50只精选股)
```

### **4. 日线扫描（每日）**
```bash
python stock_all/daily_scan.py --config stock_all/config.yaml --watchlist output/watchlist.csv
# 输出: output/daily_signals.csv (今日买入信号)
```

---

## ⚙️ 主要参数（config.yaml）

### **基础过滤**
```yaml
pre_filter:
  exclude_st: true                    # 排除ST股票
  min_avg_amount_20d: 100000000       # 1亿日均成交额
```

### **月线判定**
```yaml
monthly:
  uptrend:
    ma10_slope_min: 0.0               # MA10斜率≥0
  base_building:
    consolidation_months_min: 4       # 筑底至少4个月
```

### **周线验证**
```yaml
weekly:
  mandatory:
    ma40_slope_min: 0.0               # MA40斜率≥0
    volume_ratio_min: 1.2             # 上涨周量/下跌周量>1.2
```

### **ML排序**
```yaml
ml_ranking:
  enabled: true                       # 启用ML排序
  prophet:
    forecast_periods: 3               # 预测未来3个月
  output:
    top_n: 50                         # 输出前50只
    min_score: 60                     # 最低评分60
```

---

## 🤖 GitHub Actions自动化

推送到GitHub后，自动运行：
- **每周五16:30**：周线筛选 + ML排序
- **每日15:30**：日线信号扫描
- 结果自动提交 + Issue通知

---

## 📊 输出文件

| 文件 | 说明 | 股票数 |
|------|------|--------|
| watchlist.csv | 规则筛选结果 | ~200只 |
| ranked_stocks.csv | ML排序结果 | ~50只 |
| daily_signals.csv | 日线买入信号 | 0-20只 |

---

## 🔧 核心模块

| 文件 | 功能 |
|------|------|
| fetch_kline_history.py | K线数据获取（断点续传+重试） |
| weekly_scan.py | 月线大势+周线结构筛选 |
| run_full_scan.py | 规则筛选+ML排序完整流程 |
| daily_scan.py | 日线突破/回踩信号检测 |
| indicators.py | 技术指标计算（MA/MACD/RSI/ATR） |
| simple_feature_engineering.py | 30个核心特征提取 |
| prophet_predictor.py | Prophet时间序列预测 |
| ml_ranker.py | ML智能评分排序 |

---

## ⚠️ 注意事项

1. **数据获取**：首次需要3-6小时，断点续传支持
2. **Prophet安装**：`pip install prophet`（Windows可能需要conda）
3. **参数调优**：根据回测结果调整config.yaml
4. **风险控制**：严格止损，单笔风险≤3%

---

## 📈 策略核心

**多周期共振：**
- **月线**：判断上升趋势/底部筑底（排除下跌）
- **周线**：验证结构健康（均线+MACD+量能）
- **日线**：找买入时机（突破/回踩+放量）

**ML增强：**
- 30个核心特征 + Prophet预测
- 规则评分系统（0-100分）
- 智能排序，优中选优

---

免责声明：仅供学习研究，不构成投资建议。股市有风险，投资需谨慎。

