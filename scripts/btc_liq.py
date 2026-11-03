"""비트코인 추정 청산맵.

실제 거래소 청산 데이터(유료)를 쓰지 않고, 공개 캔들(코인베이스)로 추정합니다.
  1) 각 캔들의 거래대금 = 그 가격대에서 새로 열린 포지션으로 가정 (롱·숏 절반씩)
  2) 레버리지 분포(5~100배)에 따라 청산 가격 계산:  롱 = 진입가×(1-1/L+유지증거금), 숏 = 진입가×(1+1/L-유지증거금)
  3) 이후 가격이 그 레벨을 지나가면 이미 청산된 것으로 보고 제거
  4) 남은 물량을 가격 구간별로 합산 → 시간×가격 열지도
결과는 '어디에 청산이 몰려 있을 가능성이 큰가'를 보는 학습용 추정치입니다.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

from common import read_json, write_json

LEVERAGE = {5: 0.10, 10: 0.30, 25: 0.30, 50: 0.20, 100: 0.10}
MM = 0.005  # 유지증거금률
WINDOWS = {"24h": (900, 96), "3d": (3600, 72), "7d": (3600, 168)}  # (캔들 초, 개수)
BINS = 90
RANGE = 0.12  # 현재가 ±12%


def fetch_candles(gran: int, count: int) -> np.ndarray:
    """[[t, low, high, open, close, volume], ...] 오래된 순."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(seconds=gran * count)
    url = (f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity={gran}"
           f"&start={start.isoformat()}&end={end.isoformat()}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (personal market board)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    arr = np.array(sorted(rows, key=lambda x: x[0]), dtype=float)
    return arr[-count:]


def liq_map(c: np.ndarray, bins: int = BINS, rng: float = RANGE) -> dict:
    t, low, high, close, vol = c[:, 0], c[:, 1], c[:, 2], c[:, 4], c[:, 5]
    typ = (high + low + close) / 3
    notional = vol * typ  # USD
    last = float(close[-1])
    lo_p, hi_p = last * (1 - rng), last * (1 + rng)
    edges = np.linspace(lo_p, hi_p, bins + 1)
    T = len(c)

    # 이후 구간 최저/최고가 (청산 소진 여부 판단)
    fut_low = np.minimum.accumulate(low[::-1])[::-1]
    fut_high = np.maximum.accumulate(high[::-1])[::-1]

    heat = np.zeros((T, bins))  # 시각 j에 살아 있는 청산 물량
    long_now = np.zeros(bins)
    short_now = np.zeros(bins)
    for i in range(T):
        for L, w in LEVERAGE.items():
            amt = notional[i] * w / 2
            for side, price in (("L", typ[i] * (1 - 1 / L + MM)), ("S", typ[i] * (1 + 1 / L - MM))):
                if not (lo_p <= price < hi_p):
                    continue
                b = int((price - lo_p) / (hi_p - lo_p) * bins)
                # 언제 소진되는지: 롱은 저가가, 숏은 고가가 레벨을 건드린 첫 시점
                j = i + 1
                if side == "L":
                    hit = np.nonzero(low[i + 1:] <= price)[0]
                else:
                    hit = np.nonzero(high[i + 1:] >= price)[0]
                die = i + 1 + hit[0] if len(hit) else T
                heat[i:die, b] += amt
                if die == T:
                    (long_now if side == "L" else short_now)[b] += amt
    mx = heat.max() or 1
    return {
        "times": [int(x) for x in t],
        "price": [round(float(x), 1) for x in close],
        "high": [round(float(x), 1) for x in high],
        "low": [round(float(x), 1) for x in low],
        "edges": [round(float(x), 1) for x in edges],
        "heat": (heat / mx * 1000).round().astype(int).tolist(),
        "long_now": [round(float(x)) for x in long_now],
        "short_now": [round(float(x)) for x in short_now],
        "last": last,
        "magnet": magnets(edges, long_now, short_now, last),
    }


def magnets(edges, long_now, short_now, last) -> dict:
    mid = (edges[:-1] + edges[1:]) / 2
    below = [(float(long_now[k]), float(mid[k])) for k in range(len(mid)) if mid[k] < last]
    above = [(float(short_now[k]), float(mid[k])) for k in range(len(mid)) if mid[k] > last]
    lb = max(below) if below else (0, None)
    ab = max(above) if above else (0, None)
    return {"long_zone": lb[1], "long_amt": lb[0], "short_zone": ab[1], "short_amt": ab[0]}


def run():
    out = {}
    for name, (gran, cnt) in WINDOWS.items():
        try:
            out[name] = liq_map(fetch_candles(gran, cnt))
            print(f"  ✓ BTC {name}: {len(out[name]['times'])}개 캔들")
        except Exception as e:
            print(f"  ! BTC {name}: {e}")
    if not out:
        raise RuntimeError("BTC 캔들 수집 실패")
    from common import load_config
    rel = load_config("watchlist.json").get("btc_related", [])
    q = (read_json("quotes.json") or {}).get("quotes", {})
    write_json("btc.json", {"windows": out, "related": {t: q[t] for t in rel if t in q}})
