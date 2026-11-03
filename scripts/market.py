"""시장 체온계 + 히트맵 (미국 S&P500 / 코스피 / ETF)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from common import download_closes, load_config, market_cap, pct, read_json, write_json

US_INDICES = [
    ("^GSPC", "S&P 500"), ("^IXIC", "나스닥"), ("^DJI", "다우"), ("^RUT", "러셀2000"),
    ("^VIX", "VIX"), ("^TNX", "미 10년물"), ("DX-Y.NYB", "달러지수"), ("CL=F", "WTI"),
    ("GC=F", "금"), ("BTC-USD", "비트코인"),
]
KR_INDICES = [
    ("^KS11", "코스피"), ("^KQ11", "코스닥"), ("KRW=X", "원/달러"), ("^KS200", "코스피200"),
]


def rsi(series: pd.Series, n: int = 14) -> float | None:
    s = series.dropna()
    if len(s) < n + 1:
        return None
    d = s.diff().dropna()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up.iloc[-1] / dn.iloc[-1] if dn.iloc[-1] else math.inf
    return float(100 - 100 / (1 + rs))


def scale(x, lo, hi):
    """x를 lo→0점, hi→100점으로 선형 변환 (범위 밖은 잘라냄)."""
    if x is None:
        return None
    v = (x - lo) / (hi - lo) * 100
    return float(max(0, min(100, v)))


def index_snapshot(closes: pd.DataFrame, pairs) -> list[dict]:
    out = []
    for t, name in pairs:
        if t not in closes:
            continue
        s = closes[t].dropna()
        if len(s) < 2:
            continue
        last = float(s.iloc[-1])
        out.append({
            "ticker": t, "name": name, "last": last,
            "chg1d": pct(last, float(s.iloc[-2])),
            "chg1w": pct(last, float(s.iloc[-6])) if len(s) > 6 else None,
            "spark": [round(float(v), 4) for v in s.iloc[-30:]],
        })
    return out


def breadth(closes: pd.DataFrame, tickers: list[str], window: int = 50) -> float | None:
    cnt = above = 0
    for t in tickers:
        if t not in closes:
            continue
        s = closes[t].dropna()
        if len(s) < window:
            continue
        cnt += 1
        if s.iloc[-1] > s.iloc[-window:].mean():
            above += 1
    return above / cnt * 100 if cnt else None


def thermo_block(idx: pd.Series, breadth_pct, vol_value=None, vol_kind="VIX") -> dict:
    """지수 하나로 체온(0=극도의 공포, 100=과열) 계산."""
    s = idx.dropna()
    last = float(s.iloc[-1])
    hi52 = float(s.iloc[-252:].max())
    ma200 = float(s.iloc[-200:].mean())
    r = rsi(s)
    from_high = pct(last, hi52)
    vs200 = pct(last, ma200)
    mom20 = pct(last, float(s.iloc[-21])) if len(s) > 21 else None

    parts = [
        {"key": "rsi", "label": "RSI(14)", "value": r, "unit": "", "score": scale(r, 25, 80),
         "note": "70 이상 과매수 · 30 이하 과매도"},
        {"key": "from_high", "label": "52주 고점 대비", "value": from_high, "unit": "%", "score": scale(from_high, -20, 0),
         "note": "고점에 가까울수록 뜨거움"},
        {"key": "vs200", "label": "200일선 이격", "value": vs200, "unit": "%", "score": scale(vs200, -10, 15),
         "note": "+10% 이상은 과열 구간"},
        {"key": "mom20", "label": "20일 수익률", "value": mom20, "unit": "%", "score": scale(mom20, -10, 10),
         "note": "최근 한 달 상승 속도"},
        {"key": "breadth", "label": "50일선 위 종목", "value": breadth_pct, "unit": "%", "score": scale(breadth_pct, 20, 85),
         "note": "히트맵 종목 중 비율 · 시장의 폭"},
    ]
    if vol_value is not None:
        parts.append({"key": "vol", "label": vol_kind, "value": vol_value, "unit": "",
                      "score": scale(-vol_value, -35, -12), "note": "낮을수록 안도 · 30 이상 공포"})
    scores = [p["score"] for p in parts if p["score"] is not None]
    temp = round(sum(scores) / len(scores), 1) if scores else None
    return {"temp": temp, "label": temp_label(temp), "parts": parts}


def temp_label(t):
    if t is None:
        return "데이터 없음"
    if t < 20:
        return "저체온 · 극도의 공포"
    if t < 40:
        return "서늘함 · 경계"
    if t < 60:
        return "정상 체온"
    if t < 80:
        return "미열 · 낙관"
    return "고열 · 과열 주의"


def heatmap_block(closes: pd.DataFrame, sectors: dict, names: dict, groups: dict, caps: dict) -> list[dict]:
    tag = {t: g for g, ts in groups.items() for t in ts}
    tiles = []
    for sector, tickers in sectors.items():
        for t in tickers:
            if t not in closes:
                continue
            s = closes[t].dropna()
            if len(s) < 2:
                continue
            last = float(s.iloc[-1])
            tiles.append({
                "t": t, "name": names.get(t, t.replace(".KS", "").replace(".KQ", "")), "sector": sector,
                "cap": caps.get(t) or 1.0, "last": last, "group": tag.get(t),
                "d1": pct(last, float(s.iloc[-2])),
                "w1": pct(last, float(s.iloc[-6])) if len(s) > 6 else None,
                "m1": pct(last, float(s.iloc[-22])) if len(s) > 22 else None,
            })
    return tiles


def get_caps(tickers: list[str], prev: dict) -> dict:
    """시가총액은 매번 받지 않고 이전 값을 재사용 (월요일·첫 실행만 갱신)."""
    from common import now_kst
    refresh = now_kst().weekday() == 0 or not prev
    caps = dict(prev or {})
    for t in tickers:
        if refresh or t not in caps:
            mc = market_cap(t)
            if mc:
                caps[t] = mc
    return caps


def run(which: str = "all"):
    """which: 'us' | 'kr' | 'all'"""
    uni = load_config("universe.json")
    wl = load_config("watchlist.json")
    groups = wl["groups"]
    names = {**uni.get("kospi_names", {}), **wl.get("names", {})}

    sp = [t for ts in uni["sp500"].values() for t in ts]
    kp = [t for ts in uni["kospi"].values() for t in ts]
    etf = [t for ts in uni["etf"].values() for t in ts]
    extra = [t for ts in groups.values() for t in ts] + wl.get("btc_related", [])
    idx = [t for t, _ in US_INDICES + KR_INDICES]

    print("· 시세 다운로드")
    closes = download_closes(sp + kp + etf + extra + idx)
    if closes.empty:
        raise RuntimeError("시세를 받지 못했습니다")
    # 마지막 행이 대부분 비어 있으면(한쪽 시장만 열린 날) 종목별 dropna로 처리되므로 그대로 둠

    prev = read_json("heatmap.json") or {}
    caps = get_caps(sp + kp + etf, prev.get("caps", {}))

    old_t = read_json("thermometer.json") or {}
    vix = closes["^VIX"].dropna().iloc[-1] if "^VIX" in closes else None
    thermo = {
        "us": old_t.get("us"), "kr": old_t.get("kr"),
    }
    if which in ("us", "all") and "^GSPC" in closes:
        thermo["us"] = {
            **thermo_block(closes["^GSPC"], breadth(closes, sp), float(vix) if vix is not None else None, "VIX"),
            "indices": index_snapshot(closes, US_INDICES),
            "asof": str(closes["^GSPC"].dropna().index[-1].date()),
        }
    if which in ("kr", "all") and "^KS11" in closes:
        thermo["kr"] = {
            **thermo_block(closes["^KS11"], breadth(closes, kp)),
            "indices": index_snapshot(closes, KR_INDICES),
            "asof": str(closes["^KS11"].dropna().index[-1].date()),
        }
    # 추이 기록 (최근 60회)
    hist = old_t.get("history", [])
    from common import now_kst
    hist.append({"at": now_kst().isoformat(timespec="minutes"),
                 "us": (thermo["us"] or {}).get("temp"), "kr": (thermo["kr"] or {}).get("temp")})
    thermo["history"] = hist[-60:]
    write_json("thermometer.json", thermo)

    heat = {
        "caps": caps,
        "sp500": heatmap_block(closes, uni["sp500"], names, groups, caps),
        "kospi": heatmap_block(closes, uni["kospi"], names, groups, caps),
        "etf": heatmap_block(closes, uni["etf"], names, groups, caps),
    }
    write_json("heatmap.json", heat)

    # 관심종목 시세 (캘린더·실적·BTC 섹션에서 사용)
    quotes = {}
    for t in set(extra):
        if t in closes:
            s = closes[t].dropna()
            if len(s) >= 2:
                quotes[t] = {"last": float(s.iloc[-1]), "d1": pct(float(s.iloc[-1]), float(s.iloc[-2])),
                             "w1": pct(float(s.iloc[-1]), float(s.iloc[-6])) if len(s) > 6 else None}
    write_json("quotes.json", {"quotes": quotes, "names": names, "groups": groups})
    return thermo
