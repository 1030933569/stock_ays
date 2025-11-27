"""
股票筛选系统 - API 服务
- 提供数据 API 供其他应用调用
- 提供简洁的状态查看界面
- 数据更新由 GitHub Actions 自动完成
"""

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
import os
from datetime import datetime
from pathlib import Path
import pandas as pd

app = Flask(__name__)
CORS(app)  # 允许跨域

# 目录配置
OUTPUT_DIR = Path("output")
KLINE_DIR = Path("kline_data")

# 股票名称缓存
_stock_names_cache = None


def load_stock_names() -> dict:
    """加载股票名称映射表"""
    global _stock_names_cache
    if _stock_names_cache is not None:
        return _stock_names_cache
    
    names_file = KLINE_DIR / "stock_names.csv"
    if not names_file.exists():
        return {}
    
    try:
        df = pd.read_csv(names_file, dtype={'code': str})
        df['code'] = df['code'].apply(lambda x: str(x).zfill(6))
        _stock_names_cache = dict(zip(df['code'], df['name']))
        return _stock_names_cache
    except Exception:
        return {}


def load_csv(filename: str) -> pd.DataFrame:
    """加载 CSV 文件"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return pd.DataFrame()
    try:
        # 将 code 列作为字符串读取，避免前导零丢失
        df = pd.read_csv(file_path, dtype={'code': str})
        # 确保股票代码是6位，补零
        if 'code' in df.columns:
            df['code'] = df['code'].apply(lambda x: str(x).zfill(6) if pd.notna(x) else x)
            # 合并股票名称
            stock_names = load_stock_names()
            if stock_names:
                df['name'] = df['code'].map(stock_names).fillna(df.get('name', ''))
        return df
    except Exception:
        return pd.DataFrame()


def get_file_update_time(filename: str) -> str:
    """获取文件更新时间"""
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        mtime = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    return "无数据"


# ==================== Web 界面 ====================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QuantScope | 智能选股系统</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-card: #1a2234;
            --border: #2d3748;
            --text-primary: #f0f4f8;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-yellow: #f59e0b;
            --accent-cyan: #06b6d4;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
        }
        /* Header */
        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-purple) 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        .logo-text {
            font-size: 1.5em;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-cyan) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header-status {
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--text-secondary);
            font-size: 0.9em;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        /* Main Content */
        .main {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }
        /* Stats Row */
        .stats-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
        }
        .stat-card.blue::before { background: var(--accent-blue); }
        .stat-card.green::before { background: var(--accent-green); }
        .stat-card.purple::before { background: var(--accent-purple); }
        .stat-card.yellow::before { background: var(--accent-yellow); }
        .stat-label {
            font-size: 0.85em;
            color: var(--text-muted);
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-value {
            font-size: 2em;
            font-weight: 700;
            color: var(--text-primary);
        }
        .stat-sub {
            font-size: 0.8em;
            color: var(--text-secondary);
            margin-top: 4px;
        }
        /* Grid Layout */
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }
        .grid-3 {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
        }
        /* Cards */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }
        .card-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-title {
            font-size: 1em;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .card-badge {
            font-size: 0.75em;
            padding: 2px 8px;
            border-radius: 4px;
            background: var(--accent-blue);
            color: white;
        }
        .card-body { padding: 0; }
        /* Table */
        .table {
            width: 100%;
            border-collapse: collapse;
        }
        .table th, .table td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        .table th {
            font-size: 0.75em;
            font-weight: 500;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: rgba(0,0,0,0.2);
        }
        .table tr:hover { background: rgba(255,255,255,0.02); }
        .table tr:last-child td { border-bottom: none; }
        .code {
            font-family: 'JetBrains Mono', monospace;
            color: var(--accent-cyan);
            font-weight: 500;
        }
        .tag {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: 500;
        }
        .tag-green { background: rgba(16,185,129,0.15); color: var(--accent-green); }
        .tag-blue { background: rgba(59,130,246,0.15); color: var(--accent-blue); }
        .tag-yellow { background: rgba(245,158,11,0.15); color: var(--accent-yellow); }
        .tag-purple { background: rgba(139,92,246,0.15); color: var(--accent-purple); }
        .score {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
        }
        .score-high { color: var(--accent-green); }
        .score-mid { color: var(--accent-yellow); }
        .price { color: var(--accent-cyan); }
        /* API Section */
        .api-card { margin-top: 24px; }
        .api-endpoint {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            transition: background 0.2s;
        }
        .api-endpoint:hover { background: rgba(255,255,255,0.02); }
        .api-endpoint:last-child { border-bottom: none; }
        .api-method {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7em;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
            background: var(--accent-green);
            color: white;
            margin-right: 12px;
            min-width: 50px;
            text-align: center;
        }
        .api-path {
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-primary);
            flex: 1;
        }
        .api-desc {
            color: var(--text-muted);
            font-size: 0.85em;
        }
        /* Footer */
        .footer {
            text-align: center;
            padding: 24px;
            color: var(--text-muted);
            font-size: 0.85em;
            border-top: 1px solid var(--border);
            margin-top: 24px;
        }
        /* Trend Distribution */
        .trend-bar {
            display: flex;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 12px;
        }
        .trend-up { background: var(--accent-green); }
        .trend-base { background: var(--accent-blue); }
        .trend-legend {
            display: flex;
            gap: 16px;
            margin-top: 8px;
            font-size: 0.8em;
        }
        .trend-legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            color: var(--text-secondary);
        }
        .trend-legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 2px;
        }
        /* Empty State */
        .empty {
            padding: 40px;
            text-align: center;
            color: var(--text-muted);
        }
        /* Responsive */
        @media (max-width: 1024px) {
            .stats-row { grid-template-columns: repeat(2, 1fr); }
            .grid-2, .grid-3 { grid-template-columns: 1fr; }
        }
        @media (max-width: 640px) {
            .stats-row { grid-template-columns: 1fr; }
            .header { padding: 12px 16px; }
            .main { padding: 16px; }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">
            <div class="logo-icon">📊</div>
            <span class="logo-text">QuantScope</span>
        </div>
        <div class="header-status">
            <span class="status-dot"></span>
            <span>系统运行中 · 数据自动更新</span>
        </div>
    </header>
    
    <main class="main">
        <!-- Stats Overview -->
        <div class="stats-row">
            <div class="stat-card blue">
                <div class="stat-label">观察池</div>
                <div class="stat-value">{{ watchlist_count }}</div>
                <div class="stat-sub">周线筛选候选股</div>
            </div>
            <div class="stat-card green">
                <div class="stat-label">今日信号</div>
                <div class="stat-value">{{ signals_count }}</div>
                <div class="stat-sub">日线触发买点</div>
            </div>
            <div class="stat-card purple">
                <div class="stat-label">ML精选</div>
                <div class="stat-value">{{ ranked_count }}</div>
                <div class="stat-sub">智能排序Top股</div>
            </div>
            <div class="stat-card yellow">
                <div class="stat-label">上升趋势</div>
                <div class="stat-value">{{ trend_dist.get('UPTREND', 0) }}</div>
                <div class="stat-sub">月线多头排列</div>
            </div>
        </div>
        
        <!-- Trend Distribution -->
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <span class="card-title">📈 趋势分布</span>
                <span style="color: var(--text-muted); font-size: 0.85em;">更新: {{ watchlist_time }}</span>
            </div>
            <div style="padding: 16px 20px;">
                {% set total = trend_dist.get('UPTREND', 0) + trend_dist.get('BASE_BUILDING', 0) %}
                {% if total > 0 %}
                {% set up_pct = (trend_dist.get('UPTREND', 0) / total * 100)|round|int %}
                <div class="trend-bar">
                    <div class="trend-up" style="width: {{ up_pct }}%"></div>
                    <div class="trend-base" style="width: {{ 100 - up_pct }}%"></div>
                </div>
                <div class="trend-legend">
                    <div class="trend-legend-item">
                        <div class="trend-legend-dot trend-up"></div>
                        <span>上升趋势 {{ trend_dist.get('UPTREND', 0) }} ({{ up_pct }}%)</span>
                    </div>
                    <div class="trend-legend-item">
                        <div class="trend-legend-dot trend-base"></div>
                        <span>底部筑底 {{ trend_dist.get('BASE_BUILDING', 0) }} ({{ 100 - up_pct }}%)</span>
                    </div>
                </div>
                {% else %}
                <div class="empty">暂无数据</div>
                {% endif %}
            </div>
        </div>
        
        <!-- Main Grid -->
        <div class="grid-2">
            <!-- Daily Signals -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">🎯 日线信号</span>
                    <span class="card-badge">{{ signals_count }} 只</span>
                </div>
                <div class="card-body">
                    {% if signals %}
                    <table class="table">
                        <thead>
                            <tr>
                                <th>代码</th>
                                <th>名称</th>
                                <th>类型</th>
                                <th>入场价</th>
                                <th>风险</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for s in signals[:8] %}
                            <tr>
                                <td><span class="code">{{ s.code }}</span></td>
                                <td style="max-width:80px;overflow:hidden;text-overflow:ellipsis;">{{ s.name or '-' }}</td>
                                <td>
                                    {% if s.trigger_type == 'BREAKOUT' %}
                                    <span class="tag tag-green">突破</span>
                                    {% else %}
                                    <span class="tag tag-blue">回踩</span>
                                    {% endif %}
                                </td>
                                <td><span class="price">¥{{ "%.2f"|format(s.entry_price) }}</span></td>
                                <td><span class="tag tag-yellow">{{ s.risk_pct }}%</span></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <div class="empty">今日暂无触发信号</div>
                    {% endif %}
                </div>
            </div>
            
            <!-- ML Ranked -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">🏆 ML精选 Top10</span>
                    <span class="card-badge">{{ ranked_count }} 只</span>
                </div>
                <div class="card-body">
                    {% if ranked %}
                    <table class="table">
                        <thead>
                            <tr>
                                <th>代码</th>
                                <th>名称</th>
                                <th>评分</th>
                                <th>趋势</th>
                                <th>预测</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for r in ranked[:10] %}
                            <tr>
                                <td><span class="code">{{ r.code }}</span></td>
                                <td style="max-width:80px;overflow:hidden;text-overflow:ellipsis;">{{ r.name or '-' }}</td>
                                <td>
                                    <span class="score {% if r.ml_score >= 75 %}score-high{% else %}score-mid{% endif %}">
                                        {{ r.ml_score }}
                                    </span>
                                </td>
                                <td>
                                    {% if r.monthly_trend == 'UPTREND' %}
                                    <span class="tag tag-green">上升</span>
                                    {% else %}
                                    <span class="tag tag-blue">筑底</span>
                                    {% endif %}
                                </td>
                                <td>
                                    {% if r.prophet_forecast_return is defined and r.prophet_forecast_return > 0 %}
                                    <span style="color: var(--accent-green);">+{{ "%.1f"|format(r.prophet_forecast_return) }}%</span>
                                    {% elif r.prophet_forecast_return is defined %}
                                    <span style="color: var(--accent-red);">{{ "%.1f"|format(r.prophet_forecast_return) }}%</span>
                                    {% else %}
                                    <span style="color: var(--text-muted);">-</span>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <div class="empty">暂无ML排序数据</div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <!-- API Documentation -->
        <div class="card api-card">
            <div class="card-header">
                <span class="card-title">🔗 API 接口</span>
                <span style="color: var(--text-muted); font-size: 0.85em;">RESTful · JSON</span>
            </div>
            <div class="card-body">
                <div class="api-endpoint">
                    <span class="api-method">GET</span>
                    <span class="api-path">/api/watchlist</span>
                    <span class="api-desc">观察池数据 · ?limit=N&trend=UPTREND&min_score=N</span>
                </div>
                <div class="api-endpoint">
                    <span class="api-method">GET</span>
                    <span class="api-path">/api/signals</span>
                    <span class="api-desc">日线触发信号 · ?trigger_type=BREAKOUT</span>
                </div>
                <div class="api-endpoint">
                    <span class="api-method">GET</span>
                    <span class="api-path">/api/ranked</span>
                    <span class="api-desc">ML精选排序 · ?limit=N&min_ml_score=N</span>
                </div>
                <div class="api-endpoint">
                    <span class="api-method">GET</span>
                    <span class="api-path">/api/stock/{code}</span>
                    <span class="api-desc">查询单只股票详情</span>
                </div>
                <div class="api-endpoint">
                    <span class="api-method">GET</span>
                    <span class="api-path">/api/summary</span>
                    <span class="api-desc">数据摘要统计</span>
                </div>
            </div>
        </div>
    </main>
    
    <footer class="footer">
        <p>⚠️ 免责声明：本系统仅供学习研究使用，不构成投资建议 · 股市有风险，投资需谨慎</p>
        <p style="margin-top: 8px; color: var(--text-muted);">Powered by QuantScope · Data updated by GitHub Actions</p>
    </footer>
</body>
</html>
"""


@app.route('/')
def index():
    """主页 - 数据概览"""
    watchlist = load_csv("watchlist.csv")
    signals = load_csv("daily_signals.csv")
    ranked = load_csv("ranked_stocks.csv")
    
    # 趋势分布
    trend_dist = {}
    if not watchlist.empty and 'monthly_trend' in watchlist.columns:
        trend_dist = watchlist['monthly_trend'].value_counts().to_dict()
    
    return render_template_string(
        HTML_TEMPLATE,
        watchlist_count=len(watchlist),
        watchlist_time=get_file_update_time("watchlist.csv"),
        signals_count=len(signals),
        signals_time=get_file_update_time("daily_signals.csv"),
        signals=signals.to_dict('records') if not signals.empty else [],
        ranked_count=len(ranked),
        ranked_time=get_file_update_time("ranked_stocks.csv"),
        ranked=ranked.to_dict('records') if not ranked.empty else [],
        trend_dist=trend_dist
    )


# ==================== 数据 API ====================

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route('/api/watchlist')
def api_watchlist():
    """
    获取观察池数据
    参数: limit, trend (UPTREND/BASE_BUILDING), min_score
    """
    df = load_csv("watchlist.csv")
    
    if df.empty:
        return jsonify({"count": 0, "data": [], "error": "数据不存在"})
    
    # 筛选
    trend = request.args.get('trend')
    min_score = request.args.get('min_score', type=int)
    limit = request.args.get('limit', type=int)
    
    if trend and 'monthly_trend' in df.columns:
        df = df[df['monthly_trend'] == trend]
    
    if min_score and 'weekly_score' in df.columns:
        df = df[df['weekly_score'] >= min_score]
    
    if limit:
        df = df.head(limit)
    
    return jsonify({
        "count": len(df),
        "data": df.to_dict('records'),
        "updated_at": get_file_update_time("watchlist.csv")
    })


@app.route('/api/signals')
def api_signals():
    """
    获取日线触发信号
    参数: limit, trigger_type (BREAKOUT/PULLBACK)
    """
    df = load_csv("daily_signals.csv")
    
    if df.empty:
        return jsonify({"count": 0, "data": [], "message": "今日无触发信号"})
    
    trigger_type = request.args.get('trigger_type')
    limit = request.args.get('limit', type=int)
    
    if trigger_type and 'trigger_type' in df.columns:
        df = df[df['trigger_type'] == trigger_type]
    
    if limit:
        df = df.head(limit)
    
    return jsonify({
        "count": len(df),
        "data": df.to_dict('records'),
        "updated_at": get_file_update_time("daily_signals.csv")
    })


@app.route('/api/ranked')
def api_ranked():
    """
    获取 ML 排序精选股
    参数: limit, min_ml_score
    """
    df = load_csv("ranked_stocks.csv")
    
    if df.empty:
        return jsonify({"count": 0, "data": [], "error": "数据不存在"})
    
    min_ml_score = request.args.get('min_ml_score', type=float)
    limit = request.args.get('limit', type=int)
    
    if min_ml_score and 'ml_score' in df.columns:
        df = df[df['ml_score'] >= min_ml_score]
    
    if limit:
        df = df.head(limit)
    
    return jsonify({
        "count": len(df),
        "data": df.to_dict('records'),
        "updated_at": get_file_update_time("ranked_stocks.csv")
    })


@app.route('/api/stock/<code>')
def api_stock(code: str):
    """查询单只股票信息"""
    result = {"code": code}
    
    watchlist = load_csv("watchlist.csv")
    if not watchlist.empty and 'code' in watchlist.columns:
        match = watchlist[watchlist['code'].astype(str) == str(code)]
        if not match.empty:
            result['watchlist'] = match.iloc[0].to_dict()
    
    signals = load_csv("daily_signals.csv")
    if not signals.empty and 'code' in signals.columns:
        match = signals[signals['code'].astype(str) == str(code)]
        if not match.empty:
            result['signal'] = match.iloc[0].to_dict()
    
    ranked = load_csv("ranked_stocks.csv")
    if not ranked.empty and 'code' in ranked.columns:
        match = ranked[ranked['code'].astype(str) == str(code)]
        if not match.empty:
            result['ranked'] = match.iloc[0].to_dict()
    
    if len(result) == 1:
        return jsonify({"error": f"未找到股票 {code}"}), 404
    
    return jsonify(result)


@app.route('/api/summary')
def api_summary():
    """获取数据摘要"""
    watchlist = load_csv("watchlist.csv")
    signals = load_csv("daily_signals.csv")
    ranked = load_csv("ranked_stocks.csv")
    
    summary = {
        "watchlist": {
            "count": len(watchlist),
            "updated_at": get_file_update_time("watchlist.csv"),
        },
        "signals": {
            "count": len(signals),
            "updated_at": get_file_update_time("daily_signals.csv"),
            "data": signals.to_dict('records') if not signals.empty else []
        },
        "ranked": {
            "count": len(ranked),
            "updated_at": get_file_update_time("ranked_stocks.csv"),
            "top_5": ranked.head(5).to_dict('records') if not ranked.empty else []
        }
    }
    
    if not watchlist.empty and 'monthly_trend' in watchlist.columns:
        summary['watchlist']['trend_distribution'] = watchlist['monthly_trend'].value_counts().to_dict()
    
    return jsonify(summary)


# ==================== 启动 ====================

if __name__ == '__main__':
    OUTPUT_DIR.mkdir(exist_ok=True)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
