# Roadmap / 路线图

本路线图用于说明 A股观察池 · A-Share Watchpool 的开源维护方向。项目定位为公开行情数据研究、纸面模拟与策略审计框架，不提供投资建议，不连接券商接口，不产生真实买卖指令。
This roadmap outlines the open-source maintenance direction for A-Share Watchpool. The project is positioned as a public market data research, paper simulation, and strategy audit framework. It does not provide investment advice, does not connect to broker interfaces, and does not generate real trading commands.

## v0.9.1：文档措辞与合规表达优化 / Documentation and Compliance Wording Optimization

- 统一 README、免责声明和文档中的项目定位。
  Align the project positioning across README, disclaimer, and documentation.
- 将“选股”“交易决策”等容易误解的表达调整为观察样本、纸面模拟和策略审计语义。
  Refine potentially misleading terms like "stock selection" and "trading decision" into "watchlist entry", "paper simulation", and "strategy audit".
- 明确公开数据、无券商连接、无真实交易指令的边界。
  Clearly define the boundaries: public data, no broker connection, and no real trading commands.

## v0.9.2：增加离线示例数据和示例报告 / Add Offline Example Data and Sample Reports

- 增加脱敏或虚构的 `examples/` 示例数据。
  Add anonymized or fictional example data in `examples/`.
- 提供离线可读的样例报告结构。
  Provide offline readable sample report structures.
- 让新贡献者无需联网行情数据即可理解关键 JSON 字段。
  Enable new contributors to understand key JSON fields without needing active market data feeds.

## v0.9.3：增加测试覆盖和 CI / Expand Test Coverage and CI

- 增加免责声明和示例数据 schema 的基础测试。
  Add basic tests for disclaimers and example data schemas.
- 增加 GitHub Actions，在 push 和 pull request 时运行 pytest。
  Configure GitHub Actions to run pytest on push and pull request events.
- 逐步覆盖数据健康检查、报告渲染和策略审计接口。
  Gradually cover data health checks, report rendering, and strategy audit interfaces.

## v1.0.0：稳定 CLI、数据管道、纸面模拟和策略审计接口 / Stable CLI, Data Pipeline, Paper Sim, and Strategy Audit Interfaces

- 稳定命令行入口和运行参数。
  Stabilize CLI entrypoints and execution arguments.
- 稳定公开数据管道的输入输出格式。
  Stabilize input/output formats for public data pipelines.
- 稳定纸面模拟记录接口。
  Stabilize paper simulation record interfaces.
- 稳定策略审计报告字段和示例。
  Stabilize strategy audit report fields and examples.

## v1.1.0：引入大模型政策催化剂分析 / Integrate LLM for Policy Catalyst Analysis

- 引入大模型语义分析接口，替代原有的正则关键词匹配。
  Integrate LLM semantic analysis interfaces to replace static regex keyword matching for news catalysts.
- 自动提取宏观政策与行业催化剂的情感倾向，为观察样本的 `driver_score` 提供更智能的加分逻辑。
  Automatically extract sentiments from macro policies and industry catalysts to provide intelligent scoring for `driver_score`.
- 编写 Mock 测试以确保离线测试流水线依然保持绿色。
  Write mock test suites to ensure the offline CI pipeline remains green.

## v1.2.0：开发大模型策略安全与合规审计工具 / Develop LLM Strategy Security and Compliance Auditor

- 利用大模型静态分析用户自定义策略脚本。
  Leverage LLM static analysis to scan user-defined strategy Python scripts.
- 自动识别并拦截包含实盘交易接口（如 EasyTrader 等券商连接库）或硬编码敏感凭证（如 API keys, passwords）的危险代码。
  Automatically identify and intercept hazardous code containing live trading endpoints (e.g. broker API libraries) or hardcoded credentials.
- 增强沙盒框架的合规性保护。
  Strengthen the compliance safeguards of the quantitative research sandbox.

