# 快速上手指南

本文档帮助你在 Windows 系统上从零开始运行 A股观察池。

---

## 环境要求

| 要求 | 版本 |
|------|------|
| 操作系统 | Windows 10/11（PowerShell 5.1+） |
| Python | 3.10 及以上 |
| 网络 | 能访问 AKShare / 东方财富（国内网络即可） |

---

## 安装步骤

### 第一步：克隆仓库

```bash
git clone https://github.com/your-username/a-share-watchpool.git
cd a-share-watchpool
```

### 第二步：安装 Python 依赖

```bash
pip install -r requirements.txt
```

验证 akshare 是否正常：

```python
python -c "import akshare as ak; print(ak.__version__)"
```

### 第三步：初始化工作空间目录

```powershell
# 在 workspace/ 下创建运行时目录（这些目录被 .gitignore 排除，不会上传）
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

---

## 运行第一次盘前 Pipeline

### 方式一：使用 PowerShell 脚本（推荐）

```powershell
# 设置变量
$ROOT = (Resolve-Path "workspace").Path   # 绝对路径
$DATE = (Get-Date -Format "yyyyMMdd")     # 今天日期

# 运行盘前 Stage
powershell -File "scripts\run_daily_pipeline.ps1" -Stage pre_market -Root $ROOT -Date $DATE
```

运行成功后检查：

```powershell
# 检查数据健康状态
Get-Content "workspace\data\watchpool\${DATE}_pre_market\data_health.json" | python -c "
import json, sys
d = json.load(sys.stdin)
print('健康状态:', d.get('health_status'))
print('可排名:', d.get('can_rank_paper_watch'))
"
```

### 方式二：生成盘前 HTML 日报

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
| `AShareWatchpool-0840-PreMarket` | 工作日 08:40 | 盘前数据采集 |
| `AShareWatchpool-1506-PostClose` | 工作日 15:06 | 收盘后快照 |
| `AShareWatchpool-1630-ReviewFill` | 工作日 16:30 | T+1 结果填充 + Dashboard 更新 |

---

## 纸面模拟盘

模拟盘用于跟踪策略观察候选的实际涨跌表现，**不连接券商，不产生真实订单**。

```powershell
$SIM = "workspace\paper-sim\scripts\paper_sim_portfolio.py"

# 初始化账户（初始资金 10 万）
python $SIM init

# 每日 14:45 决策（仅使用当日日报中的 tradable_candidates）
python $SIM decide --stage late_confirm

# 查看当前持仓与净值
python $SIM status
```

---

## 常见问题

### Q: 运行时提示网络错误？

A: AKShare 依赖访问东方财富、新浪等接口，如网络受限，可配置代理：

```powershell
$env:HTTP_PROXY  = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
```

### Q: `data_health.json` 显示 `warning`？

A: 说明数据源部分失败（执行质量或风险检查未完成）。此时 `can_rank_paper_watch=false`，不会生成主榜候选，属于正常保护机制，等待下个交易日重新运行即可。

### Q: `validation_errors` 非空？

A: 报告无效，检查数据源后重新运行 Pipeline，不要手动修改 HTML。

### Q: 如何添加自定义行业主题映射？

A: 编辑 `workspace/config/industry_theme_map.json`，按现有格式添加股票代码到主题的映射。

---

## 下一步

- 查看 [选股模型说明](selection-model.md)，了解打分逻辑
- 查看 [数据来源说明](data-sources.md)，了解数据质量控制
- 积累 20+ 有效 T+3 样本后，运行策略审计：

```powershell
python scripts\audit_strategy.py `
  --db workspace\data\watchpool\watchpool.sqlite `
  --html-output workspace\reports\dashboard\strategy_audit.html
```
