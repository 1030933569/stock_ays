# Render 部署指南

## 📋 部署方式选择

根据项目特点，这是一个定时任务系统，Render提供以下部署方式：

### 方式一：Cron Jobs（推荐）✅

适合定时运行的任务，每周筛选一次，每日扫描信号。

**优点：**
- 自动定时执行
- 按使用付费
- 配置简单

**缺点：**
- 需要付费计划（免费计划不支持Cron Jobs）
- 数据不持久化（每次运行需要重新获取）

### 方式二：Background Worker

持续运行的后台服务，可以自己实现定时逻辑。

**优点：**
- 免费计划可用
- 可以实现更复杂的调度逻辑
- 数据可以在内存中持久化

**缺点：**
- 需要自己实现调度逻辑
- 一直运行会消耗资源

---

## 🚀 部署步骤

### 准备工作

1. **将代码推送到GitHub**

```bash
# 初始化git仓库（如果还没有）
git init
git add .
git commit -m "Initial commit for Render deployment"

# 推送到GitHub
git remote add origin https://github.com/你的用户名/stock_Ays.git
git branch -M main
git push -u origin main
```

2. **处理数据文件问题**

⚠️ **重要：** `kline_data` 文件夹有16260个CSV文件，非常大！

**选项A：** 不提交数据文件到Git（推荐）
- `.gitignore` 已配置忽略 `kline_data/`
- 每次运行时重新获取数据（首次需要3-6小时）

**选项B：** 使用外部存储
- 使用Render的持久化磁盘（付费）
- 或使用云存储（S3、OSS等）

---

### 方式一：使用Cron Jobs部署（推荐）

1. **登录 Render Dashboard**
   - 访问 https://dashboard.render.com/

2. **连接GitHub仓库**
   - 点击 "New +"
   - 选择 "Cron Job"
   - 连接你的GitHub仓库

3. **配置周线筛选任务**

```yaml
Name: stock-weekly-scan
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: bash start_weekly.sh
Schedule: 0 8 * * 5
# 每周五 16:00 北京时间（8:00 UTC）
```

4. **配置日线扫描任务**

```yaml
Name: stock-daily-scan
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: bash start_daily.sh
Schedule: 0 8 * * 1-5
# 周一到周五 16:00 北京时间（8:00 UTC）
```

5. **环境变量（可选）**

```bash
PYTHON_VERSION=3.11.0
TZ=Asia/Shanghai
```

---

### 方式二：使用Background Worker部署

1. **创建调度脚本**

创建 `scheduler.py`：

```python
import schedule
import time
import subprocess
from datetime import datetime

def run_weekly_scan():
    print(f"[{datetime.now()}] 开始周线筛选...")
    subprocess.run(["python", "stock_all/run_full_scan.py", "--config", "stock_all/config.yaml"])

def run_daily_scan():
    print(f"[{datetime.now()}] 开始日线扫描...")
    subprocess.run(["python", "stock_all/daily_scan.py", "--config", "stock_all/config.yaml", 
                   "--watchlist", "output/watchlist.csv"])

# 每周五15:30运行周线筛选
schedule.every().friday.at("15:30").do(run_weekly_scan)

# 周一到周五15:30运行日线扫描
schedule.every().monday.at("15:30").do(run_daily_scan)
schedule.every().tuesday.at("15:30").do(run_daily_scan)
schedule.every().wednesday.at("15:30").do(run_daily_scan)
schedule.every().thursday.at("15:30").do(run_daily_scan)
schedule.every().friday.at("15:30").do(run_daily_scan)

if __name__ == "__main__":
    print("股票筛选调度器已启动...")
    while True:
        schedule.run_pending()
        time.sleep(60)
```

2. **添加依赖**

在 `requirements.txt` 中添加：
```
schedule>=1.2.0
```

3. **部署到Render**

```yaml
Type: Background Worker
Name: stock-scheduler
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: python scheduler.py
```

---

### 方式三：使用 Web Service + 手动触发

如果你想要一个Web界面来手动触发任务：

1. **创建 Flask Web App**

```python
# app.py
from flask import Flask, jsonify
import subprocess

app = Flask(__name__)

@app.route('/run-weekly')
def run_weekly():
    subprocess.Popen(["python", "stock_all/run_full_scan.py", 
                     "--config", "stock_all/config.yaml"])
    return jsonify({"status": "started", "task": "weekly_scan"})

@app.route('/run-daily')
def run_daily():
    subprocess.Popen(["python", "stock_all/daily_scan.py", 
                     "--config", "stock_all/config.yaml", 
                     "--watchlist", "output/watchlist.csv"])
    return jsonify({"status": "started", "task": "daily_scan"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
```

2. **部署配置**

```yaml
Type: Web Service
Name: stock-web-service
Environment: Python 3
Build Command: pip install -r requirements.txt && pip install flask
Start Command: python app.py
```

---

## ⚙️ 配置建议

### 1. 数据持久化

如果需要持久化数据（避免每次重新获取）：

1. 在Render中添加持久化磁盘
2. 挂载到 `/app/kline_data`
3. 首次运行后数据会保存

### 2. 时区配置

Render默认使用UTC时间，需要转换：
- 北京时间 15:30 = UTC 07:30
- 修改 `render.yaml` 中的schedule

### 3. 通知配置

可以集成通知服务：
- 企业微信
- 钉钉
- Telegram
- Email

在脚本中添加通知逻辑。

---

## 💰 费用估算

### Cron Jobs
- 免费计划：不支持
- Starter计划：$7/月，可运行Cron Jobs

### Background Worker
- 免费计划：512MB RAM，可用
- Starter计划：$7/月，512MB RAM

### Web Service（如果使用方式三）
- 免费计划：512MB RAM，自动休眠
- Starter计划：$7/月，不休眠

---

## 🔧 故障排查

### 问题1：Prophet安装失败

```bash
# 在Dockerfile中已包含必要的系统依赖
# 如果还有问题，可以尝试：
pip install pystan==2.19.1.1
pip install prophet
```

### 问题2：数据文件过大

**解决方案A：** 使用增量更新
- 只获取最新数据
- 不保存完整历史

**解决方案B：** 使用云存储
- 将数据上传到S3/OSS
- 运行时下载

### 问题3：运行超时

Render有执行时间限制：
- 调整 `--delay` 参数加快数据获取
- 分批处理股票

---

## 📝 后续优化

1. **添加结果通知**
   - 每日信号推送到手机
   - 周线筛选结果邮件通知

2. **Web仪表板**
   - 显示筛选结果
   - 可视化图表
   - 历史回测

3. **数据库存储**
   - 使用PostgreSQL存储结果
   - 历史数据分析

4. **API接口**
   - 提供REST API
   - 第三方集成

---

## 📞 获取帮助

- Render文档: https://render.com/docs
- Python部署: https://render.com/docs/deploy-flask
- Cron Jobs: https://render.com/docs/cronjobs

---

免责声明：本系统仅供学习研究使用，不构成投资建议。

