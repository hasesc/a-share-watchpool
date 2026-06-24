# Quick Start Guide

This document helps you run the A-Share Watchpool from scratch on a Windows system. The project is designed solely for public market data research, paper simulation, and strategy audit. It does not connect to broker interfaces and does not generate real trading commands.

---

## Environment Requirements

| Requirement | Version |
|-------------|---------|
| Operating System | Windows 10/11 (PowerShell 5.1+) |
| Python | 3.10 and above |
| Network | Ability to access public data sources such as AKShare / Eastmoney |

---

## Installation Steps

### Step 1: Clone the Repository

```powershell
git clone https://github.com/hasesc/a-share-watchpool.git
cd a-share-watchpool
```

### Step 2: Install Python Dependencies

```powershell
pip install -r requirements.txt
```

Verify that `akshare` is working properly:

```powershell
python -c "import akshare as ak; print(ak.__version__)"
```

### Step 3: Initialize Workspace Directories

```powershell
New-Item -ItemType Directory -Force -Path @(
  "workspace\data\watchpool",
  "workspace\reports\daily",
  "workspace\reports\dashboard",
  "workspace\reports\health",
  "workspace\logs",
  "workspace\paper-sim\data",
  "workspace\paper-sim\reports"
)
```

These directories are used for local runtime data. Examples and tests do not depend on live market data connection results.

---

## Running Your First Pre-Market Pipeline

### Method 1: Using the PowerShell Script

```powershell
$ROOT = (Resolve-Path "workspace").Path
$DATE = (Get-Date -Format "yyyyMMdd")

powershell -File "scripts\run_daily_pipeline.ps1" -Stage pre_market -Root $ROOT -Date $DATE
```

After a successful run, check the output:

```powershell
Get-Content "workspace\data\watchpool\${DATE}_pre_market\data_health.json" | python -c "
import json, sys
d = json.load(sys.stdin)
print('Health Status:', d.get('health_status'))
print('Can Rank Watchlist:', d.get('can_rank_paper_watch'))
"
```

### Method 2: Generating Pre-Market HTML Reports

```powershell
python workspace\scripts\render_watchpool_light.py --root workspace pre-market
```

Check if the report is valid:

```powershell
Get-Content "workspace\reports\daily\${DATE}\pre_market_run_summary.json" | python -c "
import json, sys
d = json.load(sys.stdin)
errors = d.get('validation_errors', [])
print('OK' if not errors else f'Errors: {errors}')
"
```

Report output location: `workspace/reports/daily/<yyyymmdd>/pre_market_light.html`

---

## Automation (Windows Task Scheduler)

Install the daily automatic tasks with a single command:

```powershell
powershell -File "scripts\install_windows_tasks.ps1" -Root (Resolve-Path "workspace").Path
```

Installed Tasks:

| Task Name | Trigger Time | Description |
|-----------|--------------|-------------|
| `AShareWatchpool-0840-PreMarket` | Workdays 08:40 | Pre-market public data collection |
| `AShareWatchpool-1506-PostClose` | Workdays 15:06 | Post-close snapshot |
| `AShareWatchpool-1630-ReviewFill` | Workdays 16:30 | T+1 result filling + Dashboard update |

---

## Paper Simulation

Paper simulation is used to record the performance of watchlist entries on subsequent trading days. **It does not connect to any broker interfaces and does not generate real orders or trading commands.**

```powershell
$SIM = "workspace\paper-sim\scripts\paper_sim_portfolio.py"

# Initialize paper simulation portfolio (fictional funds, local simulation only)
python $SIM init

# Generate daily 14:45 paper simulation decisions (uses tradable_candidates from the daily report)
python $SIM decide --stage late_confirm

# View current paper simulation status
python $SIM status
```

---

## FAQ

### Q: Network error during execution?

A: AKShare relies on accessing public interfaces of Eastmoney, Sina, etc. If your network is restricted, you can configure a proxy:

```powershell
$env:HTTP_PROXY  = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
```

### Q: `data_health.json` shows a `warning`?

A: This indicates that the data source partially failed (execution quality or risk checks were incomplete). In this case, `can_rank_paper_watch=false`, and the system will not generate a primary watchlist. This is a normal protective mechanism. Simply wait for the next trading day and rerun.

### Q: `validation_errors` is not empty?

A: The report is invalid. Check the data source and rerun the pipeline. Do not manually modify the HTML files.

### Q: How do I add custom industry theme mappings?

A: Edit `workspace/config/industry_theme_map.json` following the existing format to map stock symbols to themes. This mapping is used for research tags only and does not represent investment recommendations.

---

## Next Steps

- See [Watchlist Construction Model Explanation](selection-model-en.md) to understand the scoring logic.
- See [Data Sources Explanation](data-sources-en.md) to understand data quality controls.
- After accumulating 20+ valid T+3 samples, run the strategy audit:

```powershell
python scripts\audit_strategy.py `
  --db workspace\data\watchpool\watchpool.sqlite `
  --html-output workspace\reports\dashboard\strategy_audit.html
```
