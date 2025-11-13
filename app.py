"""
Flask Web应用 - 用于Render Web Service部署
提供Web界面和API接口手动触发任务
"""

from flask import Flask, jsonify, render_template_string, request, send_file
import subprocess
import threading
import os
from datetime import datetime
from pathlib import Path
import json

app = Flask(__name__)

# 任务状态存储
task_status = {
    "weekly_scan": {"status": "idle", "last_run": None, "message": ""},
    "daily_scan": {"status": "idle", "last_run": None, "message": ""},
    "data_fetch": {"status": "idle", "last_run": None, "message": ""},
}

# 日志目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def _log_path_for(task_name: str) -> Path:
    mapping = {
        "weekly_scan": LOG_DIR / "weekly.log",
        "daily_scan": LOG_DIR / "daily.log",
        "data_fetch": LOG_DIR / "data_fetch.log",
    }
    return mapping.get(task_name, LOG_DIR / f"{task_name}.log")


def run_task_background(task_name, command, description):
    """在后台运行任务"""
    global task_status
    
    task_status[task_name]["status"] = "running"
    task_status[task_name]["message"] = f"正在执行: {description}"
    
    log_file_path = _log_path_for(task_name)

    # 记录任务开始
    try:
        with open(log_file_path, "a", encoding="utf-8") as lf:
            lf.write("\n" + "=" * 80 + "\n")
            lf.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行：{description}\n")
            lf.write("=" * 80 + "\n")
    except Exception:
        pass

    try:
        # 实时写入日志（同时输出到文件和控制台）
        print(f"\n{'='*80}")
        print(f"▶️  开始执行: {description}")
        print(f"{'='*80}\n")
        
        with open(log_file_path, "a", encoding="utf-8") as lf:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # 同时输出到文件和控制台
            for line in process.stdout:
                lf.write(line)
                lf.flush()
                print(line, end='', flush=True)  # 输出到 Render 日志
            
            ret = process.wait(timeout=3600)

        if ret == 0:
            task_status[task_name]["status"] = "success"
            task_status[task_name]["message"] = f"{description} 执行成功"
        else:
            task_status[task_name]["status"] = "failed"
            task_status[task_name]["message"] = f"{description} 执行失败（返回码 {ret}）"

    except subprocess.TimeoutExpired:
        task_status[task_name]["status"] = "failed"
        task_status[task_name]["message"] = f"{description} 执行超时"
        try:
            process.kill()
        except Exception:
            pass
    except Exception as e:
        task_status[task_name]["status"] = "failed"
        task_status[task_name]["message"] = f"{description} 执行异常: {str(e)}"
    
    task_status[task_name]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票筛选系统</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 40px;
            font-size: 1.1em;
        }
        .task-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .task-card {
            border: 2px solid #e0e0e0;
            border-radius: 15px;
            padding: 25px;
            transition: all 0.3s;
        }
        .task-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .task-title {
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }
        .task-desc {
            color: #666;
            margin-bottom: 15px;
            line-height: 1.6;
        }
        .task-status {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            margin-bottom: 15px;
            font-weight: 500;
        }
        .status-idle { background: #e0e0e0; color: #666; }
        .status-running { background: #ffd54f; color: #f57f17; animation: pulse 1.5s infinite; }
        .status-success { background: #81c784; color: #2e7d32; }
        .status-failed { background: #e57373; color: #c62828; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        .btn {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover { transform: scale(1.05); }
        .btn-primary:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        .last-run {
            font-size: 0.85em;
            color: #999;
            margin-top: 10px;
        }
        .message {
            font-size: 0.9em;
            color: #555;
            margin-top: 10px;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 5px;
            min-height: 40px;
        }
        .logs {
            margin-top: 12px;
            background: #0b1020;
            color: #d6e2ff;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            padding: 12px;
            border-radius: 8px;
            height: 200px;
            overflow: auto;
            white-space: pre-wrap;
        }
        .footer {
            text-align: center;
            color: #999;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }
        .refresh-btn {
            text-align: center;
            margin-bottom: 30px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📈 股票筛选系统</h1>
        <div class="subtitle">智能选股 · 把握机会</div>
        
        <div class="refresh-btn">
            <button class="btn btn-primary" onclick="location.reload()" style="width: auto; padding: 10px 30px;">
                🔄 刷新状态
            </button>
        </div>
        
        <div class="task-grid">
            <!-- 周线筛选 -->
            <div class="task-card">
                <div class="task-title">📊 周线筛选</div>
                <div class="task-desc">
                    执行月线大势判定和周线结构验证，<br>
                    从5000只股票中筛选出200只候选股，<br>
                    并通过ML算法精选出50只最优股
                </div>
                <div class="task-status status-{{ tasks.weekly_scan.status }}">
                    状态: {{ tasks.weekly_scan.status }}
                </div>
                <div class="message">{{ tasks.weekly_scan.message or '等待执行' }}</div>
                {% if tasks.weekly_scan.last_run %}
                <div class="last-run">上次运行: {{ tasks.weekly_scan.last_run }}</div>
                {% endif %}
                <button class="btn btn-primary" onclick="runTask('weekly')" 
                        {% if tasks.weekly_scan.status == 'running' %}disabled{% endif %}>
                    ▶️ 立即执行
                </button>
                <div class="logs" id="log-weekly" style="display:none;"></div>
                <button class="btn btn-primary" style="margin-top:8px" onclick="toggleLogs('weekly')">📜 查看/隐藏日志</button>
            </div>
            
            <!-- 日线扫描 -->
            <div class="task-card">
                <div class="task-title">🎯 日线扫描</div>
                <div class="task-desc">
                    基于观察池检测日线买入信号，<br>
                    识别突破型和回踩型触发点，<br>
                    计算入场价和止损价
                </div>
                <div class="task-status status-{{ tasks.daily_scan.status }}">
                    状态: {{ tasks.daily_scan.status }}
                </div>
                <div class="message">{{ tasks.daily_scan.message or '等待执行' }}</div>
                {% if tasks.daily_scan.last_run %}
                <div class="last-run">上次运行: {{ tasks.daily_scan.last_run }}</div>
                {% endif %}
                <button class="btn btn-primary" onclick="runTask('daily')"
                        {% if tasks.daily_scan.status == 'running' %}disabled{% endif %}>
                    ▶️ 立即执行
                </button>
                <div class="logs" id="log-daily" style="display:none;"></div>
                <button class="btn btn-primary" style="margin-top:8px" onclick="toggleLogs('daily')">📜 查看/隐藏日志</button>
            </div>
            
            <!-- 数据更新 -->
            <div class="task-card">
                <div class="task-title">📥 数据更新</div>
                <div class="task-desc">
                    从baostock获取最新K线数据，<br>
                    包括日线、周线、月线，<br>
                    首次运行需要3-6小时
                </div>
                <div class="task-status status-{{ tasks.data_fetch.status }}">
                    状态: {{ tasks.data_fetch.status }}
                </div>
                <div class="message">{{ tasks.data_fetch.message or '等待执行' }}</div>
                {% if tasks.data_fetch.last_run %}
                <div class="last-run">上次运行: {{ tasks.data_fetch.last_run }}</div>
                {% endif %}
                <button class="btn btn-primary" onclick="runTask('data')"
                        {% if tasks.data_fetch.status == 'running' %}disabled{% endif %}>
                    ▶️ 立即执行
                </button>
                <div class="logs" id="log-data" style="display:none;"></div>
                <button class="btn btn-primary" style="margin-top:8px" onclick="toggleLogs('data')">📜 查看/隐藏日志</button>
            </div>
        </div>
        
        <div class="footer">
            ⚠️ 免责声明: 本系统仅供学习研究使用，不构成投资建议<br>
            股市有风险，投资需谨慎
        </div>
    </div>
    
    <script>
        function runTask(taskType) {
            fetch('/api/run/' + taskType, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    // 展开日志并开始轮询
                    toggleLogs(taskType, true);
                    pollLogs(taskType);
                    setTimeout(() => location.reload(), 1000);
                })
                .catch(error => {
                    alert('执行失败: ' + error);
                });
        }

        function toggleLogs(taskType, forceOpen=false) {
            const el = document.getElementById('log-' + taskType);
            if (forceOpen) {
                el.style.display = 'block';
                return;
            }
            el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'block' : 'none';
            if (el.style.display === 'block') {
                pollLogs(taskType);
            }
        }

        function pollLogs(taskType) {
            fetch('/api/logs/' + taskType + '?_=' + Date.now())
                .then(r => r.text())
                .then(text => {
                    const el = document.getElementById('log-' + taskType);
                    if (!el) return;
                    el.textContent = text || '(暂无输出)';
                    el.scrollTop = el.scrollHeight;
                    if (el.style.display === 'block') {
                        setTimeout(() => pollLogs(taskType), 2000);
                    }
                })
                .catch(() => {});
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """主页"""
    return render_template_string(HTML_TEMPLATE, tasks=task_status)


@app.route('/api/status')
def get_status():
    """获取所有任务状态"""
    return jsonify(task_status)


@app.route('/api/run/weekly', methods=['POST'])
def run_weekly():
    """运行周线筛选"""
    if task_status["weekly_scan"]["status"] == "running":
        return jsonify({"success": False, "message": "周线筛选正在运行中"})
    
    cmd = "cd stock_all && python run_full_scan.py --config config.yaml"
    thread = threading.Thread(
        target=run_task_background,
        args=("weekly_scan", cmd, "周线筛选和ML排序")
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "周线筛选已启动"})


@app.route('/api/run/daily', methods=['POST'])
def run_daily():
    """运行日线扫描"""
    if task_status["daily_scan"]["status"] == "running":
        return jsonify({"success": False, "message": "日线扫描正在运行中"})
    
    # 检查观察池
    if not Path("output/watchlist.csv").exists():
        return jsonify({
            "success": False,
            "message": "观察池文件不存在，请先运行周线筛选"
        })
    
    cmd = "cd stock_all && python daily_scan.py --config config.yaml --watchlist ../output/watchlist.csv"
    thread = threading.Thread(
        target=run_task_background,
        args=("daily_scan", cmd, "日线信号扫描")
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "日线扫描已启动"})


@app.route('/api/run/data', methods=['POST'])
def run_data_fetch():
    """运行数据更新"""
    if task_status["data_fetch"]["status"] == "running":
        return jsonify({"success": False, "message": "数据更新正在运行中"})
    
    cmd = "cd stock_all && python fetch_kline_history.py --output-dir ../kline_data --delay 0.05"
    thread = threading.Thread(
        target=run_task_background,
        args=("data_fetch", cmd, "K线数据更新")
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "数据更新已启动（需要3-6小时）"})


@app.route('/health')
def health():
    """健康检查"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route('/api/logs/<task>')
def get_logs(task: str):
    """返回任务日志尾部"""
    name_map = {"weekly": "weekly_scan", "daily": "daily_scan", "data": "data_fetch"}
    task_key = name_map.get(task, task)
    log_path = _log_path_for(task_key)
    if not log_path.exists():
        return "(暂无日志)"
    try:
        max_bytes = 20 * 1024
        with open(log_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes), os.SEEK_SET)
            content = f.read().decode("utf-8", errors="ignore")
        return content
    except Exception as e:
        return f"(读取日志失败: {e})"


if __name__ == '__main__':
    # 创建必要的目录
    Path("output").mkdir(exist_ok=True)
    Path("kline_data").mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    
    # 启动Flask应用
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

