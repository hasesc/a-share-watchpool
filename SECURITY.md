# Security Policy

A股观察池 · A-Share Watchpool is a public market data research, paper simulation, and strategy audit framework. It does not connect to brokers, does not place orders, and does not require real account credentials.

## Supported Scope

Security reports are welcome when they relate to:

- Accidental exposure of credentials, cookies, tokens, or account-like data.
- Unsafe handling of local files or generated reports.
- Dependency risks that affect local research workflows.
- Incorrect examples that appear to contain real personal, account, or trading data.
- Code paths that could be mistaken for real broker integration or order execution.

## Out of Scope

The project does not accept or maintain:

- Broker login, broker API, account synchronization, or automatic order execution.
- Real account data, real trading records, API keys, cookies, tokens, or personal identity data.
- Return promises, stock recommendations, follow-trading workflows, or investment advice.
- Reports that require private market data or unauthorized data sources.

## Reporting a Vulnerability

Please open a GitHub issue with a minimal description and reproduction steps. Do not include secrets, real account data, or private trading records in the issue body.

If a report involves sensitive material, first describe the category of the issue without attaching the sensitive data. The maintainer can then coordinate a safer way to reproduce the problem with fictional or redacted data.

## Maintainer Response

- Confirm whether the report is within project scope.
- Reproduce using public, fictional, or redacted data.
- Patch documentation, examples, tests, or code as appropriate.
- Add regression tests when possible.

## Data Handling Commitments

- Examples must be fictional or anonymized.
- Tests should not depend on live brokerage systems or real account data.
- CI should not require secrets.
- Runtime output under `workspace/data/`, `workspace/reports/`, and `workspace/logs/` is ignored by git and should be reviewed before sharing.
