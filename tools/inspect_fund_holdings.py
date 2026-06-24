from __future__ import annotations

import akshare as ak


CODES = ["011369", "019829", "008382", "002692", "008326", "519770"]


def main() -> int:
    for code in CODES:
        print(f"--- {code}")
        try:
            hold = ak.fund_portfolio_hold_em(symbol=code, date="2025")
            print("hold")
            print(hold.head(10).to_string())
        except Exception as exc:
            print("hold err", type(exc).__name__, exc)
        try:
            industry = ak.fund_portfolio_industry_allocation_em(symbol=code, date="2025")
            print("industry")
            print(industry.head(10).to_string())
        except Exception as exc:
            print("industry err", type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
