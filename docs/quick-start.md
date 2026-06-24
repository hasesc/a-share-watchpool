# 快速上手指南

本文档帮助你在 Windows 系统上从零开始运行 A股观察池。项目仅用于公开行情数据研究、纸面模拟和策略审计，不连接券商接口，不产生真实买卖指令。

---

## 环境要求

| 要求 | 版本 |
|------|------|
| 操作系统 | Windows 10/11（PowerShell 5.1+） |
| Python | 3.10 及以上 |
| 网络 | 能访问 AKShare / 东方财富等公开数据源 |

---

## 安装步骤

### 第一步：克隆仓库

```powershell
git clone https://github.com/hasesc/a-share-watchpool.git
cd a-share-watchpool
```

### 第二步：安装 Python 依赖

```powershell
pip install -r requirements.txt
```

验证 akshare 是否正常：

```powershell
python -c "import akshare as ak; print(ak.__version__)"
```

### 第三步：初始化工作空间目录

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

这些目录用于本地运行时数据，示例和测试不会依赖真实行情联网结果。

---

## 运行第一次盘前 Pipeline

### 方式一：使用 PowerShell 脚本

```powershell
$ROOT = (Resolve-Path "workspace").Path
$DATE = (Get-Date -Format "yyyyMMdd")

powershell -File "scripts\run_daily_pipeline.ps1" -Stage pre_market -Root $ROOT -Date $DATE
```

运行成功后检查：

```powershell
Get-Content "workspace\data\watchpool\${DATE}_pre_market\data_health.json" | python -c "
import json, sys
d = json.load(sys.stdin)
print('健康状态:', d.get('health_status'))
print('可构造观察池:', d.get('can_rank_paper_watch'))
"
```

### 方式二：生成盘前 HTML 观察报告

```powershell
python workspace\scripts\render_watchpool_light.py --root workspace pre-market
```

检查报告是否有效：

```powershell
Get-Content "workspace\reports\daily\${DATE}\pre_market_run_summary.json" | python -c "
import json, sys
d = json.load(sys.stdin)
errors = d.get('validation_errors', [])
print('OK' if not errors else f'错误: {errors}')
"
```

报告输出位置：`workspace/reports/daily/<yyyymmdd>/pre_market_light.html`

---

## 自动化（Windows 任务计划）

一键安装每日自动运行任务：

```powershell
powershell -File "scripts\install_windows_tasks.ps1" -Root (Resolve-Path "workspace").Path
```

安装后的任务：

| 任务名 | 触发时间 | 说明 |
|--------|---------|------|
| `AShareWatchpool-0840-PreMarket` | 工作日 08:40 | 盘前公开数据采集 |
| `AShareWatchpool-1506-PostClose` | 工作日 15:06 | 收盘后快照 |
| `AShareWatchpool-1630-ReviewFill` | 工作日 16:30 | T+1 结果填充 + Dashboard 更新 |

---

## 纸面模拟

纸面模拟用于记录观察样本在后续交易日的表现，**不连接任何券商接口，不产生真实订单或真实买卖指令**。

```powershell
$SIM = "workspace\paper-sim\scripts\paper_sim_portfolio.py"

# 初始化纸面模拟账户（虚构资金，仅用于本地模拟）
python $SIM init

# 生成每日 14:45 纸面模拟记录（仅使用当日报告中的 tradable_candidates）
python $SIM decide --stage late_confirm

# 查看当前纸面模拟状态
python $SIM status
```

---

## 常见问题

### Q: 运行时提示网络错误？

A: AKShare 依赖访问东方财富、新浪等公开接口，如网络受限，可配置代理：

```powershell
$env:HTTP_PROXY  = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
```

### Q: `data_health.json` 显示 `warning`？

A: 说明数据源部分失败（执行质量或风险检查未完成）。此时 `can_rank_paper_watch=false`，系统不会生成 primary watchlist，属于正常保护机制，等待下个交易日重新运行即可。

### Q: `validation_errors` 非空？

A: 报告无效，检查数据源后重新运行 Pipeline，不要手动修改 HTML。

### Q: 如何添加自定义行业主题映射？

A: 编辑 `workspace/config/industry_theme_map.json`，按现有格式添加股票代码到主题的映射。该映射只用于研究标签，不代表投资建议。

---

## 下一步

- 查看 [观察样本构造模型说明](selection-model.md)，了解打分逻辑
- 查看 [数据来源说明](data-sources.md)，了解数据质量控制
- 积累 20+ 有效 T+3 样本后，运行策略审计：

```powershell
python scripts\audit_strategy.py `
  --db workspace\data\watchpool\watchpool.sqlite `
  --html-output workspace\reports\dashboard\strategy_audit.html
```
