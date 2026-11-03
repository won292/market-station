"""갱신 진입점.

  python scripts/run.py us      미국 장 마감 후: 체온계·히트맵·캘린더·실적
  python scripts/run.py kr      한국 장 마감 후: 체온계·히트맵·캘린더
  python scripts/run.py btc     매시간: 비트코인 청산맵
  python scripts/run.py all     전부

한 섹션이 실패해도 나머지는 계속 진행하고, 실패한 섹션은 이전 데이터를 그대로 둡니다.
"""
from __future__ import annotations

import sys
import traceback

sys.path.insert(0, __import__("os").path.dirname(__file__))

from common import now_kst, read_json, write_json  # noqa: E402


def step(name, fn, *a):
    print(f"[{name}]")
    try:
        r = fn(*a)
        return True if r is None else r
    except Exception:
        traceback.print_exc()
        print(f"  ✗ {name} 실패 — 이전 데이터 유지")
        return None


def diagnosis(cal: dict) -> dict:
    """오늘의 진단서: 체온 + 오늘·내일 일정 + 급등락 종목을 규칙 기반 문장으로."""
    th = read_json("thermometer.json") or {}
    hm = read_json("heatmap.json") or {}
    today = now_kst().date().isoformat()
    lines = []
    for key, label in (("us", "미국"), ("kr", "한국")):
        b = th.get(key) or {}
        if b.get("temp") is not None:
            lines.append(f"{label} 체온 {b['temp']:.0f}° — {b['label']}")
    todays = [e for e in cal.get("events", []) if e["date"] == today]
    key_ev = [e for e in todays if e.get("level", 0) >= 3 or e["cat"] in ("fomc", "주도")]
    if key_ev:
        lines.append("오늘 주목: " + ", ".join(e["title"] for e in key_ev[:4]))
    elif todays:
        lines.append(f"오늘 일정 {len(todays)}건 · 큰 이벤트 없음")
    else:
        lines.append("오늘은 예정된 주요 일정이 없습니다")
    upcoming = [e for e in cal.get("events", []) if e["date"] > today and e.get("level", 0) >= 3]
    if upcoming:
        e = upcoming[0]
        lines.append(f"다음 큰 일정: {e['date'][5:].replace('-', '/')} {e['title']}")
    tiles = [t for t in hm.get("sp500", []) + hm.get("kospi", []) if t.get("d1") is not None]
    if tiles:
        top = max(tiles, key=lambda t: t["d1"])
        bot = min(tiles, key=lambda t: t["d1"])
        lines.append(f"최대 상승 {top['name']} {top['d1']:+.1f}% · 최대 하락 {bot['name']} {bot['d1']:+.1f}%")
    grp = [t for t in tiles if t.get("group")]
    if grp:
        avg = {}
        for t in grp:
            avg.setdefault(t["group"], []).append(t["d1"])
        lines.append("관심그룹 평균: " + " · ".join(f"{g} {sum(v)/len(v):+.1f}%" for g, v in avg.items()))
    us = (th.get("us") or {}).get("temp")
    if us is None:
        verdict = "관찰"
    elif us >= 80:
        verdict = "과열 — 추격보다 점검"
    elif us <= 20:
        verdict = "공포 — 계획된 분할 접근 점검"
    elif key_ev:
        verdict = "이벤트 대기 — 변동성 대비"
    else:
        verdict = "평온 — 원칙대로"
    return {"date": today, "lines": lines, "verdict": verdict, "chart_no": now_kst().strftime("%y%m%d-%H")}


def main(mode: str):
    import market, calendar_build, earnings, btc_liq

    done = []
    if mode in ("us", "kr", "all"):
        if step("체온계·히트맵", market.run, "all" if mode == "all" else mode):
            done += ["us", "kr"] if mode == "all" else [mode]
        cal = step("마켓 캘린더", calendar_build.run)
        if isinstance(cal, dict):
            cal["diagnosis"] = diagnosis(cal)
            write_json("calendar.json", cal)
    if mode in ("us", "all"):
        step("실적 반응", earnings.run)
    if mode in ("btc", "all") and step("BTC 청산맵", btc_liq.run):
        done.append("btc")
    status = read_json("status.json") or {}
    status.pop("sample", None)
    status.pop("updated", None)
    for k in done:  # 성공한 섹션만 갱신 시각 기록
        status[k] = now_kst().isoformat(timespec="minutes")
    write_json("status.json", status)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
