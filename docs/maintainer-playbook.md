# Maintainer Playbook

This playbook defines the maintenance workflow for A股观察池 · A-Share Watchpool as an open-source research framework.

## Project Boundary

The repository is maintained as:

- A public market data research framework.
- A paper simulation record keeper.
- A strategy audit and report generation tool.

The repository must not become:

- A broker integration project.
- An automatic order execution project.
- A stock recommendation or follow-trading service.
- A place to store real account data, real trading records, API keys, cookies, or tokens.

## Release Checklist

Before publishing a release:

1. Run tests locally.

   ```powershell
   python scripts\validate_examples.py
   python -m pytest
   ```

2. Scan for credentials or personal data with a secret scanner or a project-specific `rg` pattern kept outside committed documentation.

3. Review changed documentation for recommendation-like wording.

   ```powershell
   rg -n "荐股|收益承诺|真实买卖指令|券商接口" README.md docs DISCLAIMER.md SECURITY.md
   ```

4. Confirm examples are fictional or anonymized.

5. Confirm CI is green on the default branch.

6. Create a short release note with:

   - Scope of changes.
   - Verification command.
   - Data and compliance boundary.

Draft release notes live under `docs/releases/` until the release is ready to tag.

## Issue Triage

Use issues to track concrete maintenance work:

- `documentation`: README, docs, compliance wording, quick start.
- `examples`: fictional data, offline sample reports, schema notes.
- `tests`: pytest coverage, CI improvements, regression tests.
- `data-source`: compatibility with public data sources.
- `security`: sensitive-data handling, dependency risk, unsafe examples.

Close issues only when the corresponding change is merged, tested, and documented.

## Pull Request Review

Every PR should be checked for:

- Clear scope and rationale.
- Tests or example verification.
- No broker API, order execution, or real trading workflow.
- No return promises or investment advice.
- No secrets, cookies, personal account data, or real trading records.

## Two-Week Maintenance Targets

The immediate maintenance window should prioritize:

1. Publish v0.9.1 documentation and compliance cleanup.
2. Add offline example data and a sample report summary.
3. Add tests and CI for safety statements and example schemas.
4. Add release notes and issue-based maintenance tracking.
5. Prepare v0.9.2 with richer offline examples and report fixtures.
