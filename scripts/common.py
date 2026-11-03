"""공통 유틸: 경로, 한국시간, JSON 입출력, 야후 시세 일괄 다운로드."""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "site" / "data"
KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST)


def load_config(name: str) -> dict:
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


def clean(o):
    """NaN/inf → None, numpy 숫자 → 파이썬 숫자 (JSON 직렬화용)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        try:
            o = o.item()
        except Exception:
            pass
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


def write_json(name: str, payload: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload.setdefault("updated", now_kst().isoformat(timespec="minutes"))
    (DATA / name).write_text(
        json.dumps(clean(payload), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"  → data/{name} 저장")


def read_json(name: str) -> dict | None:
    p = DATA / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def download_closes(tickers: list[str], period: str = "14mo"):
    """여러 종목 일봉 종가를 한 번에 받아 DataFrame(열=티커)으로 반환."""
    import pandas as pd
    import yfinance as yf

    tickers = list(dict.fromkeys(tickers))
    frames = []
    for i in range(0, len(tickers), 60):
        chunk = tickers[i : i + 60]
        for attempt in range(3):
            try:
                df = yf.download(
                    chunk, period=period, interval="1d", auto_adjust=True,
                    progress=False, threads=True, group_by="column",
                )
                close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].rename(columns={"Close": chunk[0]})
                frames.append(close)
                break
            except Exception as e:  # 일시적 차단 대비 재시도
                print(f"  ! 다운로드 재시도 {attempt + 1}: {e}")
                time.sleep(5 * (attempt + 1))
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, axis=1)
    out = out.loc[:, ~out.columns.duplicated()]
    return out.sort_index()


def pct(a, b):
    try:
        if a is None or b is None or b == 0 or math.isnan(a) or math.isnan(b):
            return None
        return (a / b - 1) * 100
    except Exception:
        return None


def market_cap(ticker: str):
    import yfinance as yf

    try:
        fi = yf.Ticker(ticker).fast_info
        mc = fi.get("marketCap") if hasattr(fi, "get") else fi.market_cap
        if mc:
            return float(mc)
    except Exception:
        pass
    return None
