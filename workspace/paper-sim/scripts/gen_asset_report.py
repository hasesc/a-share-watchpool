#!/usr/bin/env python3
"""Generate a paper-sim asset update report HTML from existing data."""
from pathlib import Path
import json, html as _html
from datetime import datetime

# Path independent resolution relative to this script
script_dir = Path(__file__).resolve().parent
ROOT = script_dir.parent  # paper-sim/
PROJECT_ROOT = ROOT.parent  # workspace/
OUT = ROOT / "reports" / "asset_update_report.html"

# ── Load data ────────────────────────────────────────────────────────────────
state     = json.loads((ROOT / "data" / "state.json").read_text(encoding="utf-8"))
curve_raw = (ROOT / "data" / "equity_curve.jsonl").read_text(encoding="utf-8").strip().splitlines()
orders_raw= (ROOT / "data" / "orders.jsonl").read_text(encoding="utf-8").strip().splitlines()

# ── Load config ──────────────────────────────────────────────────────────────
curve  = [json.loads(l) for l in curve_raw if l.strip()]
orders = [json.loads(l) for l in orders_raw if l.strip()]

positions = state.get("positions") or {}
initial_cash = float(state.get("initial_cash") or 100000)
cash         = float(state.get("cash") or 0)
realized_pnl = float(state.get("realized_pnl") or 0)
last_equity  = float(state.get("last_equity") or 0)
total_return_pct = (last_equity / initial_cash - 1) * 100

updated_at   = state.get("updated_at", "")
experiment   = {"start_date": "2026-06-23", "end_date": "2026-08-23",
                "experiment_name": "a-share-paper-sim-month-001"}

# Try to load experiment info from config
cfg_path = ROOT / "config.json"
if cfg_path.exists():
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    experiment.update(cfg)

# Days elapsed
try:
    start = datetime.strptime(experiment["start_date"], "%Y-%m-%d")
    end   = datetime.strptime(experiment["end_date"],   "%Y-%m-%d")
    today = datetime.now()
    elapsed = (today - start).days
    total_days = (end - start).days
    progress_pct = min(100, round(elapsed / total_days * 100, 1))
except Exception:
    elapsed, total_days, progress_pct = 0, 60, 0

def esc(v): return _html.escape(str(v or ""))
def money(v): return f"{float(v or 0):,.2f}"
def pct(v): return f"{float(v or 0):.2f}%"
def sign_class(v):
    v = float(v or 0)
    if v > 0.005: return "up"
    if v < -0.005: return "dn"
    return "flat"

# ── Position rows ─────────────────────────────────────────────────────────────
# Calculate trading days from equity_curve and state
trading_days_set = set()
for l in curve_raw:
    if l.strip():
        try:
            c = json.loads(l)
            if "date" in c:
                trading_days_set.add(c["date"])
        except Exception:
            pass
if state.get("last_decision_date"):
    trading_days_set.add(state.get("last_decision_date"))
trading_days_sorted = sorted(list(trading_days_set))

pos_rows = ""
total_pos_val = 0.0
for code, pos in positions.items():
    shares    = int(pos.get("shares") or 0)
    avg_price = float(pos.get("avg_price") or 0)
    last_price= float(pos.get("last_price") or 0)
    cost      = shares * avg_price
    val       = shares * last_price
    total_pos_val += val
    pnl       = val - cost
    pnl_pct   = (last_price / avg_price - 1) * 100 if avg_price else 0
    sc        = sign_class(pnl_pct)

    h_type    = pos.get("holding_type", "short_term")
    h_label   = {"short_term": "短线", "medium_term": "中线", "long_term": "长线"}.get(h_type, h_type)
    h_badge   = {"short_term": "badge-short", "medium_term": "badge-medium", "long_term": "badge-long"}.get(h_type, "badge-neutral")

    tags      = pos.get("reason_tags") or []
    tags_html = "".join(f'<span class="tag">{esc(t)}</span>' for t in tags) if tags else "—"
    
    # Calculate display days: difference of trading days index between last decision date and entry date
    entry_date = pos.get("entry_date")
    current_date = state.get("last_decision_date")
    hold_d    = int(pos.get("hold_decisions") or 0)
    display_days = hold_d
    if entry_date and current_date and entry_date in trading_days_sorted and current_date in trading_days_sorted:
        idx_current = trading_days_sorted.index(current_date)
        idx_entry = trading_days_sorted.index(entry_date)
        display_days = max(0, idx_current - idx_entry)
    else:
        if entry_date and current_date:
            try:
                d_entry = datetime.strptime(entry_date, "%Y%m%d")
                d_current = datetime.strptime(current_date, "%Y%m%d")
                display_days = max(0, (d_current - d_entry).days)
            except Exception:
                pass

    entry_d   = esc(pos.get("entry_date", ""))

    pnl_sign  = "+" if pnl >= 0 else ""
    driver    = float(pos.get("driver_score") or 0)
    risk_pen  = float(pos.get("risk_penalty") or 0)
    exec_sc   = float(pos.get("execution_score") or 0)
    sector    = esc(pos.get("sector") or "—")

    pos_rows += f"""
    <tr>
      <td>
        <div class="code-cell">
          <span class="code-sym">{esc(code)}</span>
          <span class="code-name">{esc(pos.get('name') or code)}</span>
        </div>
      </td>
      <td><span class="badge {h_badge}">{h_label}</span></td>
      <td class="muted">{sector}</td>
      <td class="num">{shares}</td>
      <td class="num">{money(avg_price)}</td>
      <td class="num">{money(last_price)}</td>
      <td class="num">{money(val)}</td>
      <td class="num {sc}">{pnl_sign}{money(pnl)}<br><small>{pnl_sign}{pnl_pct:.2f}%</small></td>
      <td class="num muted">{entry_d} / {display_days}天</td>
      <td><div class="score-mini">
        <span title="driver">{driver:.0f}</span>·<span title="risk" class="dn">{risk_pen:.0f}</span>·<span title="exec">{exec_sc:.0f}</span>
      </div>{tags_html}</td>
    </tr>"""

# ── Order rows ────────────────────────────────────────────────────────────────
order_rows = ""
for o in reversed(orders):
    action = o.get("action", "")
    a_cls  = "badge-buy" if action == "BUY" else "badge-sell"
    a_label= "买入" if action == "BUY" else "卖出"
    cand   = o.get("strategy_candidate") or {}
    h_type = cand.get("holding_type") or "short_term"
    h_label= {"short_term": "短线", "medium_term": "中线", "long_term": "长线"}.get(h_type, h_type)
    h_badge= {"short_term": "badge-short", "medium_term": "badge-medium", "long_term": "badge-long"}.get(h_type, "badge-neutral")
    amount = float(o.get("amount") or 0)
    time_  = (o.get("time") or "")[:19]
    reason = esc(o.get("reason") or "")
    order_rows += f"""
    <tr>
      <td><span class="badge {a_cls}">{a_label}</span></td>
      <td class="num">{esc(o.get('date',''))}</td>
      <td class="muted small">{esc(time_)}</td>
      <td>
        <span class="code-sym">{esc(o.get('code',''))}</span>
        <span class="code-name muted">{esc(o.get('name',''))}</span>
      </td>
      <td><span class="badge {h_badge}">{h_label}</span></td>
      <td class="num">{int(o.get('shares') or 0)}</td>
      <td class="num">¥{money(o.get('price'))}</td>
      <td class="num accent">¥{money(amount)}</td>
      <td class="muted small">{reason}</td>
    </tr>"""

if not order_rows:
    order_rows = '<tr><td colspan="9" class="empty">暂无成交记录</td></tr>'

# ── Equity curve rows ─────────────────────────────────────────────────────────
curve_rows = ""
for row in curve:
    eq   = float(row.get("equity") or 0)
    dpnl = float(row.get("daily_pnl") or 0)
    dret = float(row.get("daily_return_pct") or 0)
    cum_ret = (eq / initial_cash - 1) * 100
    sc   = sign_class(dret)
    sign = "+" if dpnl >= 0 else ""
    curve_rows += f"""
    <tr>
      <td class="muted">{esc(row.get('date',''))}</td>
      <td class="muted">{esc(row.get('stage',''))}</td>
      <td class="num accent">¥{money(eq)}</td>
      <td class="num {sc}">{sign}¥{money(dpnl)}</td>
      <td class="num {sc}">{sign}{dret:.3f}%</td>
      <td class="num {'up' if cum_ret>=0 else 'dn'}">{'+' if cum_ret>=0 else ''}{cum_ret:.3f}%</td>
    </tr>"""

if not curve_rows:
    curve_rows = '<tr><td colspan="6" class="empty">暂无净值记录</td></tr>'

# ── Metric cards ──────────────────────────────────────────────────────────────
pos_pct    = total_pos_val / last_equity * 100 if last_equity else 0
total_pnl  = last_equity - initial_cash
tret_class = sign_class(total_return_pct)
tret_sign  = "+" if total_return_pct >= 0 else ""

# ── HTML ──────────────────────────────────────────────────────────────────────
now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>模拟盘资产更新报告 · {now_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:       #0a0f1e;
  --surface:  #111827;
  --card:     #151d2e;
  --border:   rgba(99,120,180,0.18);
  --accent:   #3b82f6;
  --accent2:  #60a5fa;
  --gold:     #f59e0b;
  --up:       #22c55e;
  --dn:       #ef4444;
  --flat:     #94a3b8;
  --text:     #e2e8f0;
  --muted:    #94a3b8;
  --dim:      #475569;
  --shadow:   0 4px 24px rgba(0,0,0,.4);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{
  background:var(--bg);
  color:var(--text);
  font-family:'Inter','Noto Sans SC',sans-serif;
  font-size:15px;
  line-height:1.6;
  min-height:100vh;
  background-image:
    radial-gradient(ellipse 80% 40% at 20% -10%, rgba(59,130,246,.07), transparent),
    radial-gradient(ellipse 60% 40% at 80% 110%, rgba(245,158,11,.04), transparent);
}}
.page{{width:min(1100px,calc(100vw - 32px));margin:32px auto;}}

/* Header */
.header{{
  display:flex;justify-content:space-between;align-items:center;
  padding:24px 32px;
  background:linear-gradient(135deg,rgba(17,24,39,.97),rgba(21,29,46,.93));
  border:1px solid var(--border);
  border-bottom:3px solid var(--gold);
  border-radius:16px 16px 0 0;
  backdrop-filter:blur(20px);
  box-shadow:var(--shadow);
}}
.header-left h1{{font-size:22px;font-weight:900;color:#fff;letter-spacing:-.01em;}}
.header-left h1 span{{
  background:linear-gradient(135deg,#fff 40%,var(--gold));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.header-left p{{margin-top:4px;color:var(--muted);font-size:13px;}}
.stamp{{text-align:right;font-size:13px;color:var(--dim);line-height:1.8;}}
.stamp strong{{color:var(--accent2);}}

/* Metrics */
.metrics{{
  display:grid;grid-template-columns:repeat(5,1fr);gap:1px;
  background:var(--border);
  border:1px solid var(--border);border-top:0;
}}
.metric{{
  padding:18px 20px;background:var(--surface);text-align:center;
  transition:background .2s;
}}
.metric:hover{{background:var(--card);}}
.metric-icon{{font-size:18px;margin-bottom:2px;}}
.metric-label{{color:var(--dim);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;}}
.metric-value{{margin-top:6px;font-size:20px;font-weight:800;color:var(--text);}}
.metric-value.up{{color:var(--up);}}
.metric-value.dn{{color:var(--dn);}}
.metric-value.gold{{color:var(--gold);}}
.metric-sub{{margin-top:2px;font-size:12px;color:var(--muted);}}

/* Progress bar */
.progress-bar-wrap{{
  border:1px solid var(--border);border-top:0;
  background:var(--surface);padding:14px 24px;
  display:flex;align-items:center;gap:16px;
}}
.progress-label{{font-size:13px;color:var(--muted);white-space:nowrap;}}
.progress-track{{flex:1;height:6px;background:rgba(99,120,180,.15);border-radius:3px;overflow:hidden;}}
.progress-fill{{height:100%;background:linear-gradient(90deg,var(--gold),var(--accent));border-radius:3px;transition:width .6s;}}
.progress-pct{{font-size:13px;color:var(--gold);font-weight:700;white-space:nowrap;}}

/* Section */
section{{margin-top:0;box-shadow:var(--shadow);animation:fadeUp .4s ease both;}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:translateY(0)}}}}
h2{{
  display:flex;align-items:center;gap:10px;
  margin:0;padding:13px 24px;
  background:rgba(10,15,30,.95);
  border:1px solid var(--border);border-top:0;
  color:var(--text);font-size:15px;font-weight:800;
}}
h2::before{{
  content:'';display:inline-block;
  width:3px;height:15px;border-radius:2px;
  background:linear-gradient(180deg,var(--gold),var(--accent));flex-shrink:0;
}}
.panel-gap{{margin-top:20px;}}

/* Table */
.table-wrap{{overflow-x:auto;border:1px solid var(--border);border-top:0;}}
table{{width:100%;border-collapse:collapse;}}
thead th{{
  padding:10px 14px;background:rgba(15,23,42,.9);
  color:var(--dim);font-size:12px;font-weight:700;
  text-align:left;text-transform:uppercase;letter-spacing:.05em;
  border-bottom:1px solid var(--border);
}}
tbody tr{{border-bottom:1px solid rgba(99,120,180,.08);transition:background .15s;}}
tbody tr:last-child{{border-bottom:0;}}
tbody tr:hover{{background:rgba(59,130,246,.04);}}
td{{padding:11px 14px;vertical-align:middle;}}
.num{{text-align:right;font-feature-settings:'tnum';}}
.muted{{color:var(--muted);}}
.small{{font-size:12px;}}
.empty{{text-align:center;padding:28px;color:var(--dim);font-style:italic;}}

/* Color classes */
.up{{color:var(--up);}}
.dn{{color:var(--dn);}}
.flat{{color:var(--flat);}}
.accent{{color:var(--accent2);}}

/* Code cell */
.code-cell{{display:flex;flex-direction:column;gap:1px;}}
.code-sym{{font-size:15px;font-weight:700;color:var(--text);letter-spacing:.02em;}}
.code-name{{font-size:12px;color:var(--muted);}}

/* Badges */
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;}}
.badge-short {{background:rgba(239,68,68,.15);color:#fca5a5;}}
.badge-medium{{background:rgba(245,158,11,.15);color:#fcd34d;}}
.badge-long  {{background:rgba(34,197,94,.15);color:#86efac;}}
.badge-neutral{{background:rgba(99,120,180,.15);color:#94a3b8;}}
.badge-buy  {{background:rgba(239,68,68,.2);color:#fca5a5;}}
.badge-sell {{background:rgba(34,197,94,.2);color:#86efac;}}

/* Tags */
.tag{{
  display:inline-block;margin:1px 2px;
  padding:1px 6px;border-radius:3px;
  font-size:10px;font-weight:600;
  background:rgba(99,120,180,.12);color:var(--muted);
}}

/* Score mini */
.score-mini{{
  font-size:11px;font-weight:700;
  color:var(--muted);margin-bottom:3px;
}}
.score-mini span{{font-size:12px;}}

/* Footer */
.footer{{
  margin-top:20px;padding:16px 24px;
  border:1px solid var(--border);
  background:var(--surface);border-radius:0 0 12px 12px;
  font-size:12px;color:var(--dim);text-align:center;
}}
</style>
</head>
<body>
<div class="page">

<!-- Header -->
<div class="header">
  <div class="header-left">
    <h1>📊 <span>模拟盘资产更新报告</span></h1>
    <p>实验：{esc(experiment.get('experiment_name',''))} &nbsp;·&nbsp; 纸面验证，非真实买卖</p>
  </div>
  <div class="stamp">
    <div>生成时间 <strong>{now_str}</strong></div>
    <div>数据截止 {esc(updated_at[:16] if updated_at else '—')}</div>
    <div>实验周期 {esc(experiment.get('start_date',''))} → {esc(experiment.get('end_date',''))}</div>
  </div>
</div>

<!-- Metrics -->
<div class="metrics">
  <div class="metric">
    <div class="metric-icon">💰</div>
    <div class="metric-label">总资产</div>
    <div class="metric-value gold">¥{money(last_equity)}</div>
    <div class="metric-sub">起始 ¥{money(initial_cash)}</div>
  </div>
  <div class="metric">
    <div class="metric-icon">📈</div>
    <div class="metric-label">累计收益</div>
    <div class="metric-value {tret_class}">{tret_sign}{money(total_pnl)}</div>
    <div class="metric-sub {tret_class}">{tret_sign}{total_return_pct:.3f}%</div>
  </div>
  <div class="metric">
    <div class="metric-icon">🏦</div>
    <div class="metric-label">持仓市值</div>
    <div class="metric-value">¥{money(total_pos_val)}</div>
    <div class="metric-sub">仓位 {pos_pct:.1f}%</div>
  </div>
  <div class="metric">
    <div class="metric-icon">💵</div>
    <div class="metric-label">可用现金</div>
    <div class="metric-value">¥{money(cash)}</div>
    <div class="metric-sub">占比 {(cash/last_equity*100 if last_equity else 0):.1f}%</div>
  </div>
  <div class="metric">
    <div class="metric-icon">✅</div>
    <div class="metric-label">已实现盈亏</div>
    <div class="metric-value {sign_class(realized_pnl)}">{'+' if realized_pnl>=0 else ''}¥{money(realized_pnl)}</div>
    <div class="metric-sub">持仓数 {len(positions)}</div>
  </div>
</div>

<!-- Progress bar -->
<div class="progress-bar-wrap">
  <span class="progress-label">实验进度 第{elapsed}天 / 共{total_days}天</span>
  <div class="progress-track"><div class="progress-fill" style="width:{progress_pct}%"></div></div>
  <span class="progress-pct">{progress_pct}%</span>
</div>

<!-- Positions -->
<section class="panel-gap">
  <h2>📋 当前持仓明细</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>股票</th><th>类型</th><th>板块</th><th class="num">股数</th>
          <th class="num">成本价</th><th class="num">最新价</th>
          <th class="num">市值</th><th class="num">浮动盈亏</th>
          <th class="num">建仓/持有</th><th>分数·标签</th>
        </tr>
      </thead>
      <tbody>
        {pos_rows or '<tr><td colspan="10" class="empty">暂无持仓</td></tr>'}
      </tbody>
    </table>
  </div>
</section>

<!-- Orders -->
<section class="panel-gap">
  <h2>🔁 成交记录</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>方向</th><th>日期</th><th>时间</th><th>股票</th>
          <th>类型</th><th class="num">股数</th>
          <th class="num">价格</th><th class="num">金额</th><th>原因</th>
        </tr>
      </thead>
      <tbody>{order_rows}</tbody>
    </table>
  </div>
</section>

<!-- Equity curve -->
<section class="panel-gap">
  <h2>📉 净值曲线记录</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>日期</th><th>阶段</th>
          <th class="num">总资产</th>
          <th class="num">当日盈亏</th>
          <th class="num">当日收益率</th>
          <th class="num">累计收益率</th>
        </tr>
      </thead>
      <tbody>{curve_rows}</tbody>
    </table>
  </div>
</section>

<div class="footer">
  模拟盘仅作纸面验证和学习研究，不构成投资建议，不连接券商，不给真实买卖指令。&nbsp;·&nbsp;
  实验 {esc(experiment.get('start_date',''))} ~ {esc(experiment.get('end_date',''))}
</div>

</div>
</body>
</html>"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html_out, encoding="utf-8")
print(f"Written: {OUT}  ({OUT.stat().st_size:,} bytes)")
