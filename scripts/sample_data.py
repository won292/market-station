"""화면 확인용 샘플 데이터 생성 (실제 시세 아님). 실제 계산 함수를 그대로 써서 로직도 함께 점검합니다."""
from __future__ import annotations

import sys
from datetime import timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import load_config, now_kst, write_json  # noqa: E402
import market, btc_liq, earnings  # noqa: E402

rng = np.random.default_rng(7)


def walk(n, start, drift=0.0005, vol=0.015):
    r = rng.normal(drift, vol, n)
    return start * np.exp(np.cumsum(r))


def main():
    uni = load_config("universe.json")
    wl = load_config("watchlist.json")
    names = {**uni["kospi_names"], **wl["names"]}
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=300)
    cols = {}
    all_t = [t for g in ("sp500", "kospi", "etf") for ts in uni[g].values() for t in ts]
    all_t += [t for ts in wl["groups"].values() for t in ts] + wl["btc_related"]
    for t in set(all_t):
        cols[t] = walk(300, rng.uniform(20, 900), drift=rng.normal(0.0006, 0.0008), vol=rng.uniform(0.01, 0.03))
    base = {"^GSPC": 6700, "^IXIC": 22800, "^DJI": 47000, "^RUT": 2450, "^VIX": 17, "^TNX": 4.1, "DX-Y.NYB": 99,
            "CL=F": 61, "GC=F": 3950, "BTC-USD": 104000, "^KS11": 4050, "^KQ11": 900, "KRW=X": 1430, "^KS200": 560}
    for t, v in base.items():
        cols[t] = walk(300, v / 1.25 if t not in ("^VIX", "KRW=X", "^TNX", "DX-Y.NYB") else v,
                       drift=0.0008 if t not in ("^VIX", "KRW=X", "^TNX", "DX-Y.NYB") else 0, vol=0.009)
    closes = pd.DataFrame(cols, index=idx)
    caps = {t: float(rng.lognormal(25.5, 1.1)) for t in all_t}
    for big, c in {"NVDA": 4.6e12, "AAPL": 4.0e12, "MSFT": 3.8e12, "GOOGL": 3.3e12, "AMZN": 2.5e12, "META": 1.9e12,
                   "AVGO": 1.6e12, "TSLA": 1.4e12, "005930.KS": 6.0e14, "000660.KS": 4.0e14}.items():
        caps[big] = c

    sp = [t for ts in uni["sp500"].values() for t in ts]
    kp = [t for ts in uni["kospi"].values() for t in ts]
    thermo = {
        "us": {**market.thermo_block(closes["^GSPC"], market.breadth(closes, sp), float(closes["^VIX"].iloc[-1]), "VIX"),
               "indices": market.index_snapshot(closes, market.US_INDICES), "asof": str(idx[-1].date())},
        "kr": {**market.thermo_block(closes["^KS11"], market.breadth(closes, kp)),
               "indices": market.index_snapshot(closes, market.KR_INDICES), "asof": str(idx[-1].date())},
        "history": [{"at": (now_kst() - timedelta(hours=12 * i)).isoformat(timespec="minutes"),
                     "us": float(np.clip(60 + 15 * np.sin(i / 6) + rng.normal(0, 3), 0, 100)),
                     "kr": float(np.clip(70 + 12 * np.cos(i / 7) + rng.normal(0, 3), 0, 100))} for i in range(40)][::-1],
        "sample": True,
    }
    write_json("thermometer.json", thermo)
    write_json("heatmap.json", {
        "sp500": market.heatmap_block(closes, uni["sp500"], names, wl["groups"], caps),
        "kospi": market.heatmap_block(closes, uni["kospi"], names, wl["groups"], caps),
        "etf": market.heatmap_block(closes, uni["etf"], names, wl["groups"], caps), "sample": True})
    quotes = {t: {"last": float(closes[t].iloc[-1]), "d1": float(rng.normal(0, 3)), "w1": float(rng.normal(0, 6))}
              for t in set(wl["btc_related"] + [t for ts in wl["groups"].values() for t in ts])}
    write_json("quotes.json", {"quotes": quotes, "names": names, "groups": wl["groups"]})

    # 캘린더
    today = now_kst().date()
    d = lambda k: (today + timedelta(days=k)).isoformat()  # noqa: E731
    ev = [
        {"id": "s1", "date": d(0), "time": "00:00", "title": "ISM 서비스업 PMI", "flag": "🇺🇸", "cat": "macro", "level": 3, "forecast": "50.8", "previous": "50.0", "actual": "51.4"},
        {"id": "s2", "date": d(0), "time": "22:15", "title": "ADP 민간고용", "flag": "🇺🇸", "cat": "macro", "level": 2, "forecast": "35K", "previous": "-32K"},
        {"id": "s3", "date": d(1), "time": None, "title": "AMD 실적 (장후)", "ticker": "AMD", "flag": "🇺🇸", "cat": "주도", "level": 2, "forecast": "EPS 1.17"},
        {"id": "s4", "date": d(1), "time": "22:30", "title": "신규 실업수당 청구", "flag": "🇺🇸", "cat": "macro", "level": 2, "forecast": "225K", "previous": "219K"},
        {"id": "s5", "date": d(2), "time": "22:30", "title": "비농업 고용", "flag": "🇺🇸", "cat": "macro", "level": 3, "forecast": "60K", "previous": "22K"},
        {"id": "s6", "date": d(2), "time": "22:30", "title": "실업률", "flag": "🇺🇸", "cat": "macro", "level": 3, "forecast": "4.3%", "previous": "4.3%"},
        {"id": "s7", "date": d(2), "time": None, "title": "코카콜라 실적 (장전)", "ticker": "KO", "flag": "🇺🇸", "cat": "방어", "level": 2, "estimated": True},
        {"id": "s8", "date": d(3), "time": "00:00", "title": "미시간대 소비심리(예비)", "flag": "🇺🇸", "cat": "macro", "level": 2, "forecast": "53.0", "previous": "53.6"},
        {"id": "s9", "date": d(4), "time": "10:30", "title": "중국 소비자물가", "flag": "🇨🇳", "cat": "macro", "level": 3, "forecast": "0.2%", "previous": "-0.3%"},
        {"id": "s10", "date": d(5), "time": None, "title": "팔란티어 실적 (장후)", "ticker": "PLTR", "flag": "🇺🇸", "cat": "탐색", "level": 2, "estimated": True},
        {"id": "s11", "date": d(5), "time": "03:00", "title": "10년물 국채 입찰", "flag": "🇺🇸", "cat": "macro", "level": 1},
        {"id": "s12", "date": d(6), "time": "22:30", "title": "소비자물가(CPI) 전월비", "flag": "🇺🇸", "cat": "macro", "level": 3, "forecast": "0.3%", "previous": "0.3%"},
        {"id": "s13", "date": d(6), "time": None, "title": "한미반도체 실적", "ticker": "042700.KS", "flag": "🇰🇷", "cat": "탐색", "level": 2, "estimated": True},
        {"id": "s14", "date": d(3), "time": None, "title": "예시: 시장 이벤트", "flag": "", "cat": "holiday", "level": 2},
    ]
    cal = {"start": d(0), "end": d(6), "events": ev, "sample": True}
    import run as runner
    cal["diagnosis"] = runner.diagnosis(cal)
    write_json("calendar.json", cal)

    # 실적 반응 — reaction_rows 로직 점검용 합성 데이터
    comps = []
    for g, ts in wl["groups"].items():
        for t in ts:
            if t in earnings.ETF_LIKE:
                continue
            px = pd.Series(walk(800, 100, vol=0.02), index=pd.bdate_range(end=pd.Timestamp.today(), periods=800))
            dates = [px.index[-30 - 63 * k] + pd.Timedelta(hours=16 if k % 2 else 7) for k in range(9)]
            ed = pd.DataFrame({"EPS Estimate": rng.uniform(0.5, 3, 9)}, index=pd.DatetimeIndex(dates).tz_localize("America/New_York"))
            ed["Reported EPS"] = ed["EPS Estimate"] * rng.normal(1.04, 0.06, 9)
            ed["Surprise(%)"] = np.nan
            rows = earnings.reaction_rows(ed, px)
            for r in rows:  # 반응을 좀 더 그럴듯하게
                r["d1"] = float(rng.normal(0.5, 6)); r["d5"] = r["d1"] + float(rng.normal(0, 4))
            d1s = [r["d1"] for r in rows]
            comps.append({"t": t, "name": names.get(t, t), "group": g, "rows": rows,
                          "avg_abs_d1": sum(map(abs, d1s)) / len(d1s), "up_ratio": sum(x > 0 for x in d1s) / len(d1s) * 100})
    write_json("earnings.json", {"companies": comps, "sample": True})

    # BTC — 실제 청산 추정 로직에 합성 캔들 투입
    win = {}
    for name, (gran, cnt) in btc_liq.WINDOWS.items():
        t0 = int(pd.Timestamp.now(tz="UTC").timestamp()) - gran * cnt
        p = walk(cnt, 104000, drift=0, vol=0.004 if gran == 900 else 0.007)
        hi = p * (1 + np.abs(rng.normal(0, 0.003, cnt))); lo = p * (1 - np.abs(rng.normal(0, 0.003, cnt)))
        c = np.column_stack([t0 + gran * np.arange(cnt), lo, hi, p, p, rng.lognormal(5, 0.6, cnt)])
        win[name] = btc_liq.liq_map(c)
    write_json("btc.json", {"windows": win, "related": {t: quotes[t] for t in wl["btc_related"]}, "sample": True})
    write_json("status.json", {"sample": True})
    print("샘플 데이터 생성 완료")


if __name__ == "__main__":
    main()
