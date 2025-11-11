# ✅ Render 部署清单

## 📋 已创建的文件

### 核心配置文件
- ✅ `requirements.txt` - Python依赖包列表
- ✅ `render.yaml` - Render自动部署配置（Cron Jobs方式）
- ✅ `Dockerfile` - Docker容器配置
- ✅ `.gitignore` - Git忽略文件配置

### 启动脚本
- ✅ `start_weekly.sh` - 周线筛选启动脚本
- ✅ `start_daily.sh` - 日线扫描启动脚本

### 应用程序
- ✅ `app.py` - Flask Web应用（Web Service方式）
- ✅ `scheduler.py` - 定时调度器（Background Worker方式）

### 文档
- ✅ `README.md` - 项目主文档
- ✅ `README_DEPLOY.md` - 详细部署文档
- ✅ `RENDER_QUICKSTART.md` - 快速部署指南
- ✅ `DEPLOY_CHECKLIST.md` - 本文件（部署清单）

---

## 🚀 下一步操作

### 第一步：推送到 GitHub

```bash
# 1. 初始化Git（如果还没有）
git init

# 2. 添加所有文件
git add .

# 3. 提交
git commit -m "Add Render deployment files"

# 4. 添加远程仓库（替换为你的GitHub仓库地址）
git remote add origin https://github.com/你的用户名/stock_Ays.git

# 5. 推送到GitHub
git branch -M main
git push -u origin main
```

### 第二步：选择部署方式

#### 🌐 方式A：Web Service（推荐新手）

**特点：** 免费、有界面、手动触发

1. 访问 https://dashboard.render.com/
2. 注册/登录账号
3. 点击 "New +" → "Web Service"
4. 选择你的GitHub仓库
5. 配置：
   ```
   Name: stock-web-app
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: python app.py
   ```
6. 点击 "Create Web Service"
7. 等待部署完成（约5-10分钟）
8. 访问分配的URL，使用Web界面

**优点：**
- ✅ 免费计划可用
- ✅ 有Web界面，操作简单
- ✅ 适合测试和手动控制

**缺点：**
- ⚠️ 需要手动点击运行
- ⚠️ 15分钟无访问会休眠

---

#### ⚙️ 方式B：Background Worker（推荐自动化）

**特点：** 免费、自动定时执行

1. 访问 https://dashboard.render.com/
2. 点击 "New +" → "Background Worker"
3. 选择你的GitHub仓库
4. 配置：
   ```
   Name: stock-scheduler
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: python scheduler.py
   ```
5. 点击 "Create Background Worker"
6. 系统会自动按时间表运行任务

**定时任务：**
- 📊 周线筛选：每周五 15:30
- 🎯 日线扫描：周一到周五 15:30
- 📥 数据更新：每周日 20:00

**优点：**
- ✅ 免费计划可用
- ✅ 自动执行，无需手动操作
- ✅ 持续运行，不会休眠

**缺点：**
- ⚠️ 一直运行消耗资源
- ⚠️ 需要配置时区

---

#### 📅 方式C：Cron Jobs（推荐生产环境）

**特点：** 按需执行、稳定（需付费）

1. 升级Render账号到 Starter 计划（$7/月）
2. 项目中已包含 `render.yaml` 配置
3. Render会自动识别并创建3个Cron Jobs：
   - `stock-weekly-scan` - 周线筛选
   - `stock-daily-scan` - 日线扫描
   - `stock-data-fetch` - 数据更新

**或手动创建：**

1. 点击 "New +" → "Cron Job"
2. 创建三个任务（参考 render.yaml）

**优点：**
- ✅ 按需执行，节省资源
- ✅ 稳定可靠
- ✅ 适合生产环境

**缺点：**
- 💰 需要付费计划

---

## 📝 部署后检查

### 1. 检查服务状态

- 进入Render Dashboard
- 查看服务是否运行正常（绿色状态）
- 查看日志（Logs标签）

### 2. 首次运行任务

**如果使用Web Service：**
1. 访问你的Render URL
2. 点击"数据更新"按钮（首次需要3-6小时）
3. 等待数据获取完成
4. 点击"周线筛选"按钮
5. 点击"日线扫描"按钮

**如果使用Background Worker：**
- 查看Logs，等待自动执行
- 或手动触发：在Shell中运行命令

**如果使用Cron Jobs：**
- 等待定时任务自动执行
- 或手动触发测试

### 3. 验证输出结果

检查是否生成了结果文件：
```bash
# 在Render Shell中运行
ls -la output/
cat output/watchlist.csv
cat output/ranked_stocks.csv
cat output/daily_signals.csv
```

---

## ⚠️ 常见问题

### 问题1：Prophet安装失败

**症状：** Build失败，提示Prophet相关错误

**解决：**
- Dockerfile中已包含必要依赖
- 如果还有问题，降级版本：`prophet==1.1.1`

### 问题2：kline_data目录不存在

**症状：** 运行时提示找不到数据目录

**解决：**
1. 首次运行需要先获取数据
2. 或使用Render Disks持久化存储

### 问题3：观察池文件不存在

**症状：** 日线扫描失败，提示watchlist.csv不存在

**解决：**
- 必须先运行周线筛选
- 正确顺序：数据更新 → 周线筛选 → 日线扫描

### 问题4：时区不对

**症状：** 任务执行时间不对

**解决：**
- Render使用UTC时间
- 北京时间需要减8小时
- 在环境变量中设置 `TZ=Asia/Shanghai`

### 问题5：内存不足

**症状：** 运行时内存溢出

**解决：**
- 免费计划只有512MB RAM
- 升级到付费计划获得更多内存
- 或减少同时处理的股票数量

---

## 🔧 可选配置

### 添加持久化存储

1. 在Render服务设置中
2. 点击 "Disks" 标签
3. 添加新磁盘：
   ```
   Name: kline-data
   Mount Path: /app/kline_data
   Size: 10GB
   ```

### 配置环境变量

在Render服务设置中添加：

```bash
# Python版本
PYTHON_VERSION=3.11.0

# 时区
TZ=Asia/Shanghai

# 通知配置（如果需要）
WEBHOOK_URL=你的webhook地址
EMAIL_TO=your@email.com

# 数据源配置
DATA_SOURCE=baostock
DELAY=0.05
```

### 添加通知功能

在脚本结束时添加通知：

```python
# 企业微信通知示例
import requests

def send_wechat_notification(content):
    webhook = os.getenv('WECHAT_WEBHOOK')
    data = {
        "msgtype": "text",
        "text": {"content": content}
    }
    requests.post(webhook, json=data)

# 在任务完成后调用
send_wechat_notification(f"周线筛选完成，发现{len(results)}只候选股")
```

---

## 📊 监控和维护

### 日常检查

1. **查看日志：**
   - 每天查看Render Logs
   - 确认任务正常执行

2. **检查结果：**
   - 定期下载输出文件
   - 验证数据质量

3. **性能监控：**
   - 关注内存使用
   - 关注执行时间

### 定期维护

1. **更新依赖：**
   ```bash
   pip list --outdated
   pip install --upgrade package_name
   ```

2. **优化参数：**
   - 根据市场变化调整config.yaml
   - 回测验证新参数

3. **备份数据：**
   - 定期备份kline_data
   - 定期备份output结果

---

## 🎉 部署完成！

恭喜！你已经完成了部署准备。

**接下来：**
1. ✅ 选择一种部署方式
2. ✅ 推送代码到GitHub
3. ✅ 在Render上创建服务
4. ✅ 运行任务，查看结果

**获取帮助：**
- 📖 查看 [RENDER_QUICKSTART.md](RENDER_QUICKSTART.md)
- 📖 查看 [README_DEPLOY.md](README_DEPLOY.md)
- 🌐 访问 https://render.com/docs

---

## 📞 支持

遇到问题？

- 📧 提交 GitHub Issue
- 💬 查看 Render 文档
- 🔍 搜索相关错误信息

---

**祝你使用愉快！📈**

**免责声明：** 本系统仅供学习研究，不构成投资建议。股市有风险，投资需谨慎！

