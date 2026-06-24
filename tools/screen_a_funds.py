from __future__ import annotations

from datetime import datetime, timedelta

import akshare as ak
import pandas as pd


def max_drawdown(nav: pd.Series) -> float:
    drawdown = (nav / nav.cummax() - 1.0) * 100.0
    return float(drawdown.min())


def main() -> int:
    rank = ak.fund_open_fund_rank_em(symbol="全部")
    rank["近1年"] = pd.to_numeric(rank["近1年"], errors="coerce")
    exclude = "债|货币|QDII|纳斯达克|标普|恒生|港股|海外|美元|原油|黄金|REIT|短债|中债|债券|同业存单"
    df = rank[
        rank["近1年"].notna()
        & ~rank["基金简称"].str.contains(exclude, regex=True, na=False)
    ].sort_values("近1年", ascending=False)

    cutoff = pd.Timestamp(datetime.now().date() - timedelta(days=366))
    rows: list[tuple[str, str, float, float, float, str]] = []
    for _, row in df.head(60).iterrows():
        code = str(row["基金代码"])
        name = str(row["基金简称"])
        try:
            nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            nav["净值日期"] = pd.to_datetime(nav["净值日期"])
            nav["单位净值"] = pd.to_numeric(nav["单位净值"], errors="coerce")
            nav = nav[nav["净值日期"] >= cutoff].dropna(subset=["单位净值"])
            if len(nav) < 80:
                continue
            mdd = max_drawdown(nav["单位净值"])
            ret = float((nav["单位净值"].iloc[-1] / nav["单位净值"].iloc[0] - 1.0) * 100.0)
            if mdd >= -20:
                rows.append(
                    (
                        code,
                        name,
                        round(float(row["近1年"]), 2),
                        round(ret, 2),
                        round(mdd, 2),
                        str(nav["净值日期"].iloc[-1].date()),
                    )
                )
        except Exception:
            continue

    print("count", len(rows))
    for item in rows[:40]:
        print("\t".join(map(str, item)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
