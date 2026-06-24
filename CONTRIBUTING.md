# Contributing / 贡献指南

感谢你关注 A股观察池 · A-Share Watchpool。本项目是公开行情数据研究、纸面模拟与策略审计框架，不是投资建议工具，也不接入真实交易系统。
Thank you for your interest in A-Share Watchpool. This project is a public market data research, paper simulation, and strategy audit framework. It is not an investment advisory tool and does not connect to real trading systems.

## 欢迎的贡献 / Welcomed Contributions

- Bug report 和可复现问题描述
  Bug reports and reproducible descriptions of issues.
- 文档改进、术语澄清和合规表达优化
  Documentation improvements, terminology clarification, and compliance phrasing optimization.
- 公开数据源兼容性改进
  Compatibility improvements for public data sources.
- 数据健康检查、报告渲染和策略审计相关测试
  Tests relating to data health checks, report rendering, and strategy audit.
- 脱敏或虚构的示例数据
  Anonymized or fictional example data.
- Windows / PowerShell 运行体验改进
  Usability and setup improvements for Windows / PowerShell environments.

## 不接受的贡献 / Unacceptable Contributions

- 真实券商接口、自动下单、账户登录或交易执行功能
  Broker logins, broker APIs, account synchronization, or automatic order execution features.
- 荐股承诺、收益承诺、跟单引导或投资建议表达
  Stock recommendations, return promises, follow-trading guides, or investment advice phrasing.
- 真实个人交易记录、真实账户数据、API key、cookie、token 或其他敏感信息
  Real personal trading records, real account data, API keys, cookies, tokens, or other sensitive information.
- 依赖未授权数据源、绕过数据服务条款或违反合规边界的实现
  Implementations relying on unauthorized data sources, bypassing data service terms, or violating compliance boundaries.

## Pull Request 要求 / Pull Request Requirements

- PR 应清楚说明改动目的和影响范围。
  PRs should clearly explain the purpose and scope of changes.
- 行为变更应附带测试，文档或示例变更应说明如何验证。
  Behavioral changes should include tests; documentation or example updates should explain how to verify.
- 测试应尽量不依赖实时联网行情，优先使用脱敏示例数据。
  Tests should avoid depending on live internet connections and prioritize using anonymized example data.
- 不要在同一个 PR 中混合无关重构和功能变更。
  Do not mix unrelated refactorings and functional changes in the same PR.
- 修改策略阈值、字段含义或报告结构时，请同步更新文档和示例。
  When modifying strategy thresholds, field definitions, or report layouts, update the documentation and examples accordingly.

## 本地测试 / Local Testing

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest
```

## 合规检查 / Compliance Verification

提交前请确认：
Please verify before submitting:

- 没有真实账户数据、真实交易数据或个人身份信息。
  No real account data, real trading records, or personally identifiable information is included.
- 没有 API key、cookie、token 等敏感信息。
  No API keys, cookies, tokens, or other sensitive details are included.
- 没有收益承诺、买卖建议或真实交易指令表达。
  No return promises, buy/sell recommendations, or real trading command phrasing is included.

