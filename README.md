# 마켓 계측소 — 설치 안내

시장 체온계 · 히트맵 · 마켓 캘린더 · 비트코인 청산맵 · 실적 반응 · 인물의 한마디를
한 화면에서 보는 개인 투자 보드입니다. GitHub가 정해진 시간마다 데이터를 모아
사이트를 새로 올리므로, 한 번 설정하면 컴퓨터를 켜 두지 않아도 계속 갱신됩니다.

처음 압축을 풀면 **샘플 데이터**가 들어 있습니다(화면 위 노란 띠). 자동 갱신이 한 번 돌면 실제 데이터로 바뀝니다.

---

## 1. 처음 설정 (약 15분, 비용 없음)

1. **GitHub 가입** — https://github.com 에서 무료 계정을 만듭니다.
2. **새 저장소 만들기** — 오른쪽 위 `+` → `New repository`
   - 이름: 예) `market-station`
   - **Public**(공개) 선택 — 무료로 사이트를 띄우고 자동 실행 시간 제한이 없습니다. 공개되는 것은 시세 데이터와 화면 코드뿐입니다.
   - `Create repository`
3. **파일 올리기** — 저장소 화면의 `uploading an existing file` 링크 → 압축을 푼 폴더 **안의 내용 전체**(`.github`, `config`, `scripts`, `site`, `README.md`, `requirements.txt`)를 끌어다 놓고 `Commit changes`.
   - `.github` 폴더는 숨김 폴더라 안 보일 수 있습니다. Mac은 Finder에서 `Cmd+Shift+.`, Windows는 탐색기 `보기 → 숨긴 항목` 체크.
4. **사이트 켜기** — 저장소 `Settings` → 왼쪽 `Pages` → `Source`를 **GitHub Actions**로 선택.
5. **첫 갱신 실행** — 저장소 `Actions` 탭 → (처음이면 `I understand… enable` 버튼) → 왼쪽 `데이터 갱신` → `Run workflow` → mode `all` → 실행.
   5~10분 뒤 초록 체크가 뜨면 `Settings → Pages` 상단에 사이트 주소(`https://아이디.github.io/market-station/`)가 표시됩니다.

이후로는 아래 일정대로 저절로 갱신됩니다.

| 언제 (한국시간) | 무엇을 |
|---|---|
| 매일 06:16 전후 (화~토) | 미국 장 마감 반영: 체온계·히트맵·캘린더·실적 반응 |
| 매일 15:46 전후 (월~금) | 한국 장 마감 반영: 체온계·히트맵·캘린더 |
| 매시 07분 | 비트코인 청산맵 |
| 페이지를 열어 둔 동안 | BTC 현재가 5분마다, 새 데이터 10분마다 확인 |

GitHub 예약 실행은 몰리는 시간대에 5~20분 늦어질 수 있습니다.

## 2. (선택) 경제지표 발표치 자동 입력

캘린더의 예상치·이전치는 바로 나오지만, **발표치**(CPI·고용·실업률 등)를 자동으로 채우려면 무료 FRED 키가 필요합니다.

1. https://fred.stlouisfed.org/docs/api/api_key.html 에서 가입 후 API 키 발급
2. 저장소 `Settings → Secrets and variables → Actions → New repository secret`
   - Name: `FRED_API_KEY`, Secret: 받은 키

## 3. 내 입맛대로 바꾸기

모두 GitHub 웹에서 파일을 열고 연필(✏️) 아이콘으로 고친 뒤 `Commit changes` 하면 몇 분 안에 반영됩니다.

| 바꾸고 싶은 것 | 파일 |
|---|---|
| 주도·방어·탐색 관심종목, BTC 관련주 | `config/watchlist.json` |
| 히트맵 종목·섹터 | `config/universe.json` |
| FOMC·휴장일 (해마다 추가) | `config/fixed_events.json` |
| 나의 한마디 | `site/content/notes.json` |
| 인물의 한마디 | `site/content/voices.json` |

티커는 야후 파이낸스 표기입니다. 코스피 `005930.KS`, 코스닥 `067310.KQ`, 미국은 그대로 `NVDA`.

## 4. 각 섹션은 어떻게 계산되나

- **체온계** — RSI, 52주 고점 대비, 200일선 이격, 20일 수익률, 50일선 위 종목 비율, VIX(미국)를 각각 0~100점으로 바꿔 평균. 20 이하 공포, 80 이상 과열.
- **히트맵** — 타일 크기는 시가총액(월요일마다 갱신), 색은 등락률(±3%에서 최대). 한국식으로 상승 빨강·하락 파랑.
- **캘린더** — ForexFactory 공개 일정(미국 전체 + 중국·일본 고영향), FOMC·휴장은 설정 파일, 실적일은 야후. ★는 날짜가 범위로만 나온 예상일.
- **오늘의 진단서** — 체온·오늘 일정·급등락 종목으로 규칙에 따라 자동 작성.
- **BTC 청산맵** — 코인베이스 공개 캔들의 거래대금을 그 가격대에서 새로 열린 포지션으로 보고, 5~100배 레버리지 분포로 청산 가격을 계산한 뒤 이미 가격이 지나간 레벨은 지웁니다. 실제 거래소 청산 데이터가 아닌 **추정치**입니다.
- **실적 반응** — 최근 8분기 발표일 기준, 발표 직전 종가 대비 1일·5일 뒤 주가. 장후 발표는 다음 거래일 반응으로 계산. 한국 종목은 야후에 실적 이력이 없으면 표시되지 않습니다.

## 5. 문제가 생기면

- `Actions` 탭에서 빨간 ✗가 뜬 실행을 열면 어느 단계가 실패했는지 보입니다. 한 섹션이 실패해도 나머지는 갱신되고, 실패한 섹션은 이전 데이터를 유지합니다.
- 야후 파이낸스는 가끔 일시적으로 막힙니다. 대부분 다음 예약 실행에서 저절로 회복됩니다.
- 60일 동안 저장소에 아무 변경이 없으면 GitHub가 예약 실행을 멈추지만, 이 보드는 매시간 데이터를 커밋하므로 해당되지 않습니다.

## 6. Netlify로 띄우고 싶다면 (선택)

Netlify에서 `Add new site → Import from GitHub` → 이 저장소 선택 → Publish directory에 `site` 입력.
다만 매시간 데이터 커밋마다 Netlify 배포가 돌아 무료 한도(월 300분)에 가까워질 수 있어, 기본값은 GitHub Pages로 두었습니다.

## 폴더 구조

```
.github/workflows/update.yml   자동 갱신 일정
config/                        관심종목·히트맵 종목·고정 일정
scripts/                       데이터 수집 (run.py가 시작점)
site/                          웹페이지 (index.html, style.css, app.js)
site/data/                     자동 생성 데이터 — 직접 고치지 마세요
site/content/                  직접 쓰는 글 (한마디, 인물 발언)
```

로컬에서 확인하려면: `pip install -r requirements.txt && python scripts/run.py all` 후 `cd site && python -m http.server` → http://localhost:8000
