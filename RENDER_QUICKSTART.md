# Render 快速部署指南 🚀

## 📌 三种部署方式对比

| 方式 | 适用场景 | 费用 | 优点 | 缺点 |
|------|---------|------|------|------|
| **Web Service + 手动触发** | 测试/手动控制 | 免费可用 | 简单、有界面 | 需要手动点击 |
| **Background Worker** | 自动定时执行 | 免费可用 | 自动化、免费 | 一直运行消耗资源 |
| **Cron Jobs** | 生产环境 | $7/月起 | 按需执行、稳定 | 需要付费 |

**推荐：** 新手先用 Web Service，熟悉后升级到 Background Worker 或 Cron Jobs。

---

## 🎯 方式一：Web Service（推荐新手）

### 特点
- ✅ 免费计划可用
- ✅ 有Web界面，可以手动点击运行任务
- ✅ 简单易用，适合测试

### 部署步骤

1. **推送代码到GitHub**

```bash
git init
git add .
git commit -m "Deploy to Render"
git remote add origin https://github.com/你的用户名/stock_Ays.git
git push -u origin main
```

2. **在Render创建Web Service**

- 访问 https://dashboard.render.com/
- 点击 "New +" → "Web Service"
- 连接你的GitHub仓库
- 配置如下：

```yaml
Name: stock-web-app
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: python app.py
```

3. **等待部署完成**

- Render会自动部署
- 部署成功后会获得一个URL，如：`https://stock-web-app.onrender.com`

4. **访问Web界面**

- 打开浏览器访问你的Render URL
- 点击按钮手动触发任务

### 注意事项

⚠️ **免费计划限制：**
- 15分钟无访问会自动休眠
- 重新访问需要等待启动（约30秒）
- 每月750小时免费运行时间

💡 **首次使用建议：**
1. 先点击"数据更新"获取K线数据（需要3-6小时）
2. 数据获取完成后，运行"周线筛选"
3. 最后运行"日线扫描"

---

## 🎯 方式二：Background Worker（推荐自动化）

### 特点
- ✅ 免费计划可用
- ✅ 自动定时执行任务
- ✅ 持续运行，不会休眠

### 部署步骤

1. **推送代码到GitHub**（同方式一）

2. **在Render创建Background Worker**

- 访问 https://dashboard.render.com/
- 点击 "New +" → "Background Worker"
- 连接你的GitHub仓库
- 配置如下：

```yaml
Name: stock-scheduler
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: python scheduler.py
```

3. **查看日志**

- 在Render Dashboard中点击服务名称
- 查看 "Logs" 标签，监控任务执行情况

### 定时任务配置

在 `scheduler.py` 中已配置：
- **周线筛选**：每周五 15:30
- **日线扫描**：周一到周五 15:30
- **数据更新**：每周日 20:00

可以根据需要修改时间。

---

## 🎯 方式三：Cron Jobs（推荐生产环境）

### 特点
- ⚠️ 需要付费计划（$7/月起）
- ✅ 按需执行，节省资源
- ✅ 更稳定，适合生产环境

### 部署步骤

1. **升级到付费计划**

- Render免费计划不支持Cron Jobs
- 需要升级到 Starter 计划或更高

2. **使用 render.yaml 部署**

项目中已包含 `render.yaml` 配置文件，Render会自动识别。

3. **或手动创建Cron Jobs**

创建三个Cron Jobs：

**周线筛选：**
```yaml
Name: stock-weekly-scan
Schedule: 30 7 * * 5  # 每周五 15:30 北京时间（7:30 UTC）
Command: bash start_weekly.sh
```

**日线扫描：**
```yaml
Name: stock-daily-scan
Schedule: 30 7 * * 1-5  # 周一到周五 15:30
Command: bash start_daily.sh
```

**数据更新：**
```yaml
Name: stock-data-update
Schedule: 0 12 * * 0  # 每周日 20:00 北京时间（12:00 UTC）
Command: cd stock_all && python fetch_kline_history.py --output-dir ../kline_data
```

---

## ⚙️ 环境变量配置（可选）

在Render的Environment Variables中添加：

```bash
# Python版本
PYTHON_VERSION=3.11.0

# 时区
TZ=Asia/Shanghai

# 通知配置（如果需要）
# WEBHOOK_URL=你的webhook地址
# EMAIL=你的邮箱
```

---

## 📊 数据持久化

### 问题
Render默认不保存数据，每次重新部署都会丢失 `kline_data` 和 `output` 目录。

### 解决方案

**方案A：使用Render Disks（推荐）**

1. 在服务设置中添加 Disk
2. 挂载点：`/app/kline_data`
3. 大小：至少10GB

**方案B：每次重新获取数据**

- 不保存数据
- 每周运行一次数据更新任务
- 适合免费计划

**方案C：使用云存储**

- 将数据上传到S3、阿里云OSS等
- 运行时从云存储下载
- 适合大规模部署

---

## 🔧 故障排查

### 问题1：Prophet安装失败

**解决：** Dockerfile中已包含必要的系统依赖。如果还有问题：

```bash
# 降级到兼容版本
pip install pystan==2.19.1.1
pip install prophet==1.1.1
```

### 问题2：数据目录不存在

**解决：** 首次运行需要先获取数据

```bash
# 手动运行数据获取
python stock_all/fetch_kline_history.py --output-dir ./kline_data
```

### 问题3：执行超时

Render有执行时间限制（免费计划较短）

**解决：**
- 减少处理的股票数量
- 增大 `--delay` 参数
- 或升级到付费计划

### 问题4：观察池文件不存在

**解决：** 运行日线扫描前必须先运行周线筛选

```bash
# 正确顺序
1. 数据更新
2. 周线筛选
3. 日线扫描
```

---

## 📈 推荐工作流程

### 首次部署
1. ✅ 部署Web Service
2. ✅ 运行"数据更新"（等待3-6小时）
3. ✅ 运行"周线筛选"（约10-30分钟）
4. ✅ 运行"日线扫描"（约5-10分钟）

### 日常使用

**手动模式（Web Service）：**
- 每周五收盘后：手动点击"周线筛选"
- 每个交易日收盘后：手动点击"日线扫描"

**自动模式（Background Worker/Cron Jobs）：**
- 无需操作，系统自动执行
- 定期查看输出结果

---

## 📂 查看结果

结果文件保存在 `output/` 目录：

- `watchlist.csv` - 周线筛选的200只候选股
- `ranked_stocks.csv` - ML排序的50只精选股
- `daily_signals.csv` - 今日买入信号

**如何访问结果文件：**

1. **通过Render Shell：**
   - 在Dashboard中打开服务
   - 点击 "Shell" 标签
   - 运行 `cat output/ranked_stocks.csv`

2. **添加文件下载功能：**

可以扩展 `app.py` 添加文件下载接口：

```python
@app.route('/download/<filename>')
def download(filename):
    return send_file(f'output/{filename}', as_attachment=True)
```

3. **发送到邮箱/微信：**

在脚本中添加通知功能，自动发送结果。

---

## 💡 进阶优化

1. **添加通知功能**
   - 企业微信机器人
   - 钉钉机器人
   - Telegram Bot
   - Email通知

2. **创建Web仪表板**
   - 可视化筛选结果
   - K线图表展示
   - 历史回测分析

3. **使用数据库**
   - PostgreSQL存储历史结果
   - 追踪股票表现
   - 策略优化

4. **API接口**
   - RESTful API
   - 第三方系统集成

---

## 📞 获取帮助

- **Render文档：** https://render.com/docs
- **Python部署：** https://render.com/docs/deploy-flask
- **问题反馈：** 在GitHub Issues中提问

---

## ⚠️ 重要提示

1. **数据获取限制：** baostock可能有访问限制，建议：
   - 使用合理的延迟（`--delay 0.05`）
   - 避免频繁请求
   - 考虑使用其他数据源

2. **免费计划限制：**
   - 15分钟无活动自动休眠
   - 每月750小时运行时间
   - 内存限制512MB

3. **时区问题：**
   - Render使用UTC时间
   - 北京时间需要减8小时
   - 建议在代码中处理时区转换

4. **安全提醒：**
   - 不要在公开仓库提交敏感信息
   - 使用环境变量存储密钥
   - 定期更新依赖包

---

## 🎉 开始部署

选择适合你的部署方式，立即开始：

- 🌐 **Web Service：** 简单快速，适合新手
- ⚙️ **Background Worker：** 自动化，免费可用
- 📅 **Cron Jobs：** 生产级，按需执行

祝你使用愉快！股市有风险，投资需谨慎！📈

