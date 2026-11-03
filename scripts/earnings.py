"""관심기업 실적 반응 히스토리: 최근 8분기 EPS 서프라이즈와 발표 후 1일·5일 주가 반응."""
from __future__ import annotations

import pandas as pd

from common import load_config, write_json

ETF_LIKE = {"SCHD", "IBIT", "SPY", "QQQ", "JEPI"}


def reaction_rows(ed: pd.DataFrame, px: pd.Series, n: int = 8) -> list[dict]:
    """ed: get_earnings_dates 결과(인덱스=발표 시각), px: 일봉 종가(인덱스=날짜)."""
    px = px.dropna()
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
    days = px.index
    rows = []
    past = ed[ed["Reported EPS"].notna()] if "Reported EPS" in ed else ed.iloc[0:0]
    for ts, r in past.sort_index(ascending=False).head(n).iterrows():
        ts = pd.Timestamp(ts)
        local = ts.tz_convert("America/New_York") if ts.tzinfo else ts
        d = pd.Timestamp(local.date())
        after_close = local.hour >= 12  # 오후 발표면 다음 거래일에 반응
        react_idx = days.searchsorted(d, side="right" if after_close else "left")
        if react_idx <= 0 or react_idx >= len(days):
            continue
        base = float(px.iloc[react_idx - 1])
        d1 = float(px.iloc[react_idx]) / base - 1
        d5 = float(px.iloc[min(react_idx + 4, len(px) - 1)]) / base - 1
        est, act = r.get("EPS Estimate"), r.get("Reported EPS")
        surprise = r.get("Surprise(%)")
        if (surprise is None or pd.isna(surprise)) and est and not pd.isna(est) and est != 0:
            surprise = (act - est) / abs(est) * 100
        rows.append({
            "date": str(d.date()), "when": "장후" if after_close else "장전",
            "eps_est": None if pd.isna(est) else float(est), "eps_act": None if pd.isna(act) else float(act),
            "surprise": None if surprise is None or pd.isna(surprise) else float(surprise),
            "d1": d1 * 100, "d5": d5 * 100,
        })
    return rows[::-1]


def run():
    import yfinance as yf

    wl = load_config("watchlist.json")
    names = {**load_config("universe.json").get("kospi_names", {}), **wl.get("names", {})}
    companies = []
    for g, tickers in wl["groups"].items():
        for t in tickers:
            if t in ETF_LIKE:
                continue
            try:
                tk = yf.Ticker(t)
                ed = tk.get_earnings_dates(limit=14)
                if ed is None or ed.empty:
                    raise ValueError("실적 발표 이력 없음")
                px = tk.history(period="3y", auto_adjust=True)["Close"]
                rows = reaction_rows(ed, px)
                if not rows:
                    raise ValueError("계산 가능한 분기 없음")
                d1s = [r["d1"] for r in rows]
                companies.append({
                    "t": t, "name": names.get(t, t), "group": g, "rows": rows,
                    "avg_abs_d1": sum(abs(x) for x in d1s) / len(d1s),
                    "up_ratio": sum(1 for x in d1s if x > 0) / len(d1s) * 100,
                })
                print(f"  ✓ {t} {len(rows)}분기")
            except Exception as e:
                print(f"  ! 실적이력 {t}: {e}")
    write_json("earnings.json", {"companies": companies})
