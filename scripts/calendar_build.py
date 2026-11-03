"""마켓 캘린더(다음 7일): 경제지표(ForexFactory 공개 피드) + FOMC + 실적 + 휴장."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import date, datetime, timedelta

from common import KST, load_config, now_kst, read_json, write_json

FF_FEEDS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]
UA = {"User-Agent": "Mozilla/5.0 (personal market board)"}

# 자주 나오는 지표 이름 한글화 (없는 것은 원문 표시)
KO = {
    "CPI m/m": "소비자물가(CPI) 전월비", "CPI y/y": "소비자물가(CPI) 전년비",
    "Core CPI m/m": "근원 CPI 전월비", "Core CPI y/y": "근원 CPI 전년비",
    "PPI m/m": "생산자물가(PPI) 전월비", "Core PPI m/m": "근원 PPI 전월비",
    "Core PCE Price Index m/m": "근원 PCE 물가 전월비", "Core PCE Price Index y/y": "근원 PCE 물가 전년비",
    "Non-Farm Employment Change": "비농업 고용", "Unemployment Rate": "실업률",
    "Average Hourly Earnings m/m": "평균 시간당 임금", "Unemployment Claims": "신규 실업수당 청구",
    "ADP Non-Farm Employment Change": "ADP 민간고용", "JOLTS Job Openings": "JOLTS 구인건수",
    "Retail Sales m/m": "소매판매 전월비", "Core Retail Sales m/m": "근원 소매판매",
    "ISM Manufacturing PMI": "ISM 제조업 PMI", "ISM Services PMI": "ISM 서비스업 PMI",
    "Flash Manufacturing PMI": "S&P 제조업 PMI(예비)", "Flash Services PMI": "S&P 서비스업 PMI(예비)",
    "Advance GDP q/q": "GDP 속보치", "Prelim GDP q/q": "GDP 잠정치", "Final GDP q/q": "GDP 확정치",
    "Prelim UoM Consumer Sentiment": "미시간대 소비심리(예비)", "Revised UoM Consumer Sentiment": "미시간대 소비심리(확정)",
    "CB Consumer Confidence": "컨퍼런스보드 소비자신뢰", "Federal Funds Rate": "FOMC 기준금리 결정",
    "FOMC Statement": "FOMC 성명", "FOMC Press Conference": "파월 의장 기자회견",
    "FOMC Meeting Minutes": "FOMC 의사록", "Fed Chair Powell Speaks": "연준 의장 연설",
    "Empire State Manufacturing Index": "뉴욕 제조업지수", "Philly Fed Manufacturing Index": "필라델피아 제조업지수",
    "Durable Goods Orders m/m": "내구재 주문", "Building Permits": "건축 허가", "Housing Starts": "주택 착공",
    "Existing Home Sales": "기존주택 판매", "New Home Sales": "신규주택 판매", "Pending Home Sales m/m": "잠정주택 판매",
    "Industrial Production m/m": "산업생산", "Trade Balance": "무역수지", "Crude Oil Inventories": "원유 재고",
    "10-y Bond Auction": "10년물 국채 입찰", "30-y Bond Auction": "30년물 국채 입찰",
    "Caixin Manufacturing PMI": "중국 차이신 제조업 PMI", "Manufacturing PMI": "제조업 PMI",
    "BOJ Policy Rate": "일본은행 기준금리", "Monetary Policy Statement": "통화정책 성명",
    "Congressional Elections": "미국 의회 선거", "Loan Officer Survey": "연준 대출담당자 서베이",
    "Construction Spending m/m": "건설지출", "ISM Manufacturing Prices": "ISM 제조업 물가",
    "ISM Services Prices": "ISM 서비스업 물가", "RCM/TIPP Economic Optimism": "TIPP 경제낙관지수",
    "Omdia Total Vehicle Sales": "자동차 판매", "API Weekly Statistical Bulletin": "API 원유 재고",
    "Final Services PMI": "S&P 서비스업 PMI(확정)", "Final Manufacturing PMI": "S&P 제조업 PMI(확정)",
    "Factory Orders m/m": "공장 주문", "Challenger Job Cuts y/y": "챌린저 감원 발표",
    "Prelim Nonfarm Productivity q/q": "노동생산성(예비)", "Prelim Unit Labor Costs q/q": "단위노동비용(예비)",
    "Natural Gas Storage": "천연가스 재고", "Consumer Credit m/m": "소비자 신용",
    "Prelim UoM Inflation Expectations": "미시간대 기대인플레(예비)", "Revised UoM Inflation Expectations": "미시간대 기대인플레(확정)",
    "Wholesale Inventories m/m": "도매 재고", "Business Inventories m/m": "기업 재고", "Import Prices m/m": "수입물가",
    "Federal Budget Balance": "연방 재정수지", "NAHB Housing Market Index": "NAHB 주택시장지수",
    "Chicago PMI": "시카고 PMI", "Richmond Manufacturing Index": "리치먼드 제조업지수", "Beige Book": "베이지북",
    "Personal Spending m/m": "개인소비", "Personal Income m/m": "개인소득", "Employment Cost Index q/q": "고용비용지수",
    "S&P/CS Composite-20 HPI y/y": "케이스-실러 주택가격", "HPI m/m": "주택가격지수", "Current Account": "경상수지",
    "Retail Sales y/y": "소매판매 전년비", "Industrial Production y/y": "산업생산 전년비", "Bank Holiday": "은행 휴일",
    "Treasury Currency Report": "재무부 환율보고서", "Core PCE Price Index": "근원 PCE 물가",
    "Tokyo Core CPI y/y": "도쿄 근원 CPI", "National Core CPI y/y": "일본 근원 CPI",
    "CPI y/y (CNY)": "중국 소비자물가", "PPI y/y": "생산자물가 전년비", "GDP q/y": "GDP 전년비",
    "New Loans": "신규 위안화 대출", "M2 Money Supply y/y": "M2 통화량",
}
SPEAKER = {
    "FOMC Member": "연준 위원", "Fed Chair": "연준 의장", "Fed Vice Chair": "연준 부의장",
    "BOJ Gov": "일본은행 총재", "PBOC Gov": "인민은행 총재", "Treasury Sec": "재무장관", "President": "대통령",
}
FOMC_TITLES = {"Federal Funds Rate", "FOMC Statement", "FOMC Press Conference", "FOMC Meeting Minutes",
               "FOMC Economic Projections"}


def ko_title(title: str, country: str) -> str:
    if title in KO:
        if country == "CNY" and title in ("CPI y/y", "PPI y/y"):
            return "중국 " + KO[title].replace("(CPI)", "").replace("(PPI)", "")
        if country == "JPY" and title in ("CPI y/y",):
            return "일본 " + KO[title]
        return KO[title]
    # "FOMC Member Williams Speaks" → "연준 위원 윌리엄스 연설" 형태
    if title.endswith(" Speaks"):
        who = title[: -len(" Speaks")]
        for k, v in SPEAKER.items():
            if who.startswith(k):
                rest = who[len(k):].strip()
                return f"{v} {rest} 연설".replace("  ", " ")
        return who + " 연설"
    return title
COUNTRY_KO = {"USD": "🇺🇸", "CNY": "🇨🇳", "JPY": "🇯🇵", "EUR": "🇪🇺", "GBP": "🇬🇧", "KRW": "🇰🇷"}
IMPACT = {"High": 3, "Medium": 2, "Low": 1, "Holiday": 0}

# FRED에서 실제치(발표치)를 가져올 지표: (시리즈, 계산 방식, 단위)
FRED_MAP = {
    "CPI m/m": ("CPIAUCSL", "mom", "%"), "CPI y/y": ("CPIAUCSL", "yoy", "%"),
    "Core CPI m/m": ("CPILFESL", "mom", "%"), "Core CPI y/y": ("CPILFESL", "yoy", "%"),
    "PPI m/m": ("PPIFIS", "mom", "%"), "Core PCE Price Index m/m": ("PCEPILFE", "mom", "%"),
    "Core PCE Price Index y/y": ("PCEPILFE", "yoy", "%"), "Unemployment Rate": ("UNRATE", "level", "%"),
    "Non-Farm Employment Change": ("PAYEMS", "diff", "K"), "Retail Sales m/m": ("RSAFS", "mom", "%"),
    "Unemployment Claims": ("ICSA", "level_k", "K"), "Industrial Production m/m": ("INDPRO", "mom", "%"),
}


def http_json(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fred_actual(title: str, event_day: date):
    key = os.environ.get("FRED_API_KEY")
    if not key or title not in FRED_MAP:
        return None
    series, how, unit = FRED_MAP[title]
    url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={series}&api_key={key}"
           f"&file_type=json&sort_order=desc&limit=14")
    try:
        obs = [o for o in http_json(url)["observations"] if o["value"] != "."]
    except Exception as e:
        print(f"  ! FRED {series}: {e}")
        return None
    if len(obs) < 13 or obs[0]["realtime_start"] < event_day.isoformat():
        return None  # 아직 이번 발표분이 반영되지 않음
    v = [float(o["value"]) for o in obs]
    if how == "mom":
        val = (v[0] / v[1] - 1) * 100
    elif how == "yoy":
        val = (v[0] / v[12] - 1) * 100
    elif how == "diff":
        val = v[0] - v[1]
    elif how == "level_k":
        val = v[0] / 1000
    else:
        val = v[0]
    return f"{val:.1f}{unit}" if unit == "%" else f"{val:.0f}{unit}"


def macro_events(countries: list[str]) -> list[dict]:
    rows = []
    for url in FF_FEEDS:
        try:
            rows += http_json(url)
        except Exception as e:
            print(f"  ! 경제지표 피드 실패 {url.rsplit('/', 1)[-1]}: {e}")
    out = []
    for r in rows:
        if r.get("country") not in countries:
            continue
        lvl = IMPACT.get(r.get("impact"), 1)
        if r.get("country") != "USD" and lvl < 3:
            continue  # 해외 지표는 '정밀(고영향)'만
        try:
            src = datetime.fromisoformat(r["date"])  # 원래 시간대(미 동부 등)
            dt = src.astimezone(KST)
        except Exception:
            continue
        title = r.get("title", "")
        cat = "fomc" if title in FOMC_TITLES else "macro"
        if lvl == 0:
            cat = "holiday"
        # 시간 미정(종일) 일정은 피드에 원래 시간대 자정으로 들어옴 → 날짜도 원래 날짜 사용
        all_day = src.hour == 0 and src.minute == 0
        day = src.date() if all_day else dt.date()
        out.append({
            "id": f"ff:{r.get('country')}:{title}:{day}",
            "date": day.isoformat(), "time": None if all_day else dt.strftime("%H:%M"),
            "title": ko_title(title, r.get("country")), "orig": title, "flag": COUNTRY_KO.get(r.get("country"), r.get("country")),
            "cat": cat, "level": lvl, "forecast": r.get("forecast") or None, "previous": r.get("previous") or None,
            "actual": r.get("actual") or None,
        })
    return out


def fixed_events(start: date, end: date) -> list[dict]:
    cfg = load_config("fixed_events.json")
    out = []
    for f in cfg.get("fomc", []):
        d = date.fromisoformat(f["date"])
        if start <= d <= end:
            out.append({"id": f"fomc:{d}", "date": d.isoformat(), "time": f.get("time"),
                        "title": "FOMC 금리 결정 · 기자회견", "flag": "🇺🇸", "cat": "fomc", "level": 3})
    for m in cfg.get("market", []):
        d = date.fromisoformat(m["date"])
        if start <= d <= end:
            out.append({"id": f"mkt:{d}:{m['title']}", "date": d.isoformat(), "time": m.get("time"),
                        "title": m["title"], "flag": "", "cat": m.get("cat", "holiday"), "level": m.get("level", 2)})
    return out


def earnings_events(groups: dict, names: dict, start: date, end: date) -> list[dict]:
    import pandas as pd
    import yfinance as yf

    out = []
    for g, tickers in groups.items():
        for t in tickers:
            try:
                tk = yf.Ticker(t)
                cal = tk.calendar or {}
                dates = cal.get("Earnings Date") or []
                if not dates:
                    continue
                d0 = pd.Timestamp(dates[0]).date()
                estimated = len(dates) > 1 and pd.Timestamp(dates[-1]).date() != d0
                if not (start - timedelta(days=1) <= d0 <= end):
                    continue
                when = None
                try:  # 발표 시각(장전/장후) 추정
                    ed = tk.get_earnings_dates(limit=6)
                    if ed is not None and len(ed):
                        for ts in ed.index:
                            if ts.date() == d0:
                                et_hour = ts.tz_convert("America/New_York").hour if ts.tzinfo else ts.hour
                                when = "장전" if et_hour < 12 else "장후"
                except Exception:
                    pass
                # 미국 장후 발표는 한국시간으로 다음날 새벽
                kst_day = d0 + timedelta(days=1) if (when == "장후" and not t.endswith((".KS", ".KQ"))) else d0
                if not (start <= kst_day <= end):
                    continue
                eps = cal.get("Earnings Average")
                out.append({
                    "id": f"earn:{t}:{d0}", "date": kst_day.isoformat(), "time": None,
                    "title": f"{names.get(t, t)} 실적" + (f" ({when})" if when else ""), "ticker": t,
                    "flag": "🇰🇷" if t.endswith((".KS", ".KQ")) else "🇺🇸",
                    "cat": g, "level": 2, "estimated": estimated,
                    "forecast": f"EPS {eps:.2f}" if isinstance(eps, (int, float)) else None,
                })
            except Exception as e:
                print(f"  ! 실적일정 {t}: {e}")
    return out


def run():
    wl = load_config("watchlist.json")
    names = {**load_config("universe.json").get("kospi_names", {}), **wl.get("names", {})}
    today = now_kst().date()
    end = today + timedelta(days=6)

    events = []
    print("· 경제지표 피드")
    events += [e for e in macro_events(wl.get("calendar_countries", ["USD"])) if today <= date.fromisoformat(e["date"]) <= end]
    events += fixed_events(today, end)
    print("· 실적 일정")
    events += earnings_events(wl["groups"], names, today, end)

    # FOMC가 피드와 고정 일정에 중복되면 고정 일정만 남김
    fomc_days = {e["date"] for e in events if e["id"].startswith("fomc:")}
    events = [e for e in events if not (e["id"].startswith("ff:") and e["cat"] == "fomc" and e["date"] in fomc_days)]

    # 이전 갱신에서 입력된 발표치 유지 + FRED로 채우기
    prev = {e["id"]: e for e in (read_json("calendar.json") or {}).get("events", [])}
    for e in events:
        if not e.get("actual") and prev.get(e["id"], {}).get("actual"):
            e["actual"] = prev[e["id"]]["actual"]
        if e["cat"] == "macro" and not e.get("actual") and date.fromisoformat(e["date"]) <= today:
            e["actual"] = fred_actual(e.get("orig", ""), date.fromisoformat(e["date"]) - timedelta(days=1))

    events.sort(key=lambda e: (e["date"], e.get("time") or "99:99", -e.get("level", 0)))
    return {"start": today.isoformat(), "end": end.isoformat(), "events": events}
