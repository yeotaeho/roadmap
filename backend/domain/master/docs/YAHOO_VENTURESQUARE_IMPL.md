# Yahoo Macro Backfill + 벤처스퀘어 구현 전략

## 📋 문서 개요

- **작성일**: 2026-05-17
- **목적**: `WOWTALE_YAHOO_ENHANCEMENT_STRATEGY.md` 미구현 항목 구현 기록
- **범위**: Phase 2(Yahoo Backfill) + Phase 3B(벤처스퀘어) 구현 완료

---

## ✅ 구현 완료 항목

### Phase 1 (이전 세션 완료)

| 항목 | 파일 | 상태 |
|------|------|------|
| Wowtale 아카이브 크롤러 | `wowtale_archive_crawler.py` | ✅ |
| 아카이브 CLI | `scripts/wowtale_backfill.py` | ✅ |
| 아카이브 라우터 | `POST /bronze/economic/wowtale-archive` | ✅ |
| 통합 테스트 | `scripts/wowtale_archive_integration_test.py` | ✅ |

### Phase 2 (이번 세션 완료)

| 항목 | 파일 | 상태 |
|------|------|------|
| Yahoo Finance Backfill | `collect_surge_history_sync()` (이전 세션 확인) | ✅ |
| Yahoo Finance Backfill 라우터 | `POST /bronze/economic/yahoo-finance?backfill=true` | ✅ |
| **Yahoo Macro Backfill** | `collect_macro_history_sync()` 신규 추가 | ✅ |
| **Yahoo Macro Backfill 서비스** | `ingest_yahoo_macro_backfill()` | ✅ |
| **Yahoo Macro Backfill 라우터** | `POST /bronze/economic/yahoo-macro-backfill` | ✅ |
| **Yahoo Backfill CLI** | `scripts/yahoo_backfill.py` | ✅ |

### Phase 3B (이번 세션 완료)

| 항목 | 파일 | 상태 |
|------|------|------|
| **벤처스퀘어 수집기** | `venturesquare_collector.py` | ✅ |
| **벤처스퀘어 서비스 메서드** | `ingest_venturesquare()` | ✅ |
| **벤처스퀘어 라우터** | `POST /bronze/economic/venturesquare` | ✅ |

### 스킵·보류 항목

| 항목 | 사유 | 비고 |
|------|------|------|
| 네이버 금융 크롤러 | 상업적 이용 법적 리스크 🔴 High | [ECONOMIC_DATA_SOURCE_STATUS.md](./ECONOMIC_DATA_SOURCE_STATUS.md) |
| 크런치베이스 API | 유료 데이터 API 라이선스 | 동일 |
| NTIS OpenAPI | 기관 소속·키 발급 | Held — MSIT·ALIO 우회 |

### 이후 구현됨 (본 문서 초안 이후)

| 항목 | 상태 |
|------|------|
| `raw_market_timeseries` + `yahoo_market_timeseries_collector.py` | ✅ 2026-05-17 — `POST /bronze/market-timeseries/yahoo`, 일 스케줄 `yahoo_market_ts` |
| 벤처스퀘어 스케줄러 | ✅ `daily_venturesquare` |

---

## 🔧 구현 상세

### 1. Yahoo Macro Backfill — `collect_macro_history_sync()`

**위치**: `yahoo_macro_collector.py` → `YahooMacroCollector` 클래스

**알고리즘**:
```
for each target in MACRO_TARGETS (8종):
    hist = yf.Ticker(ticker).history(period="1y")
    for end_idx in range(_Z_WINDOW + 1, len(hist)):
        sub = hist.iloc[:end_idx + 1]   ← 슬라이딩 윈도우
        dto = _compute_zscore_dto(target, sub)
        if dto: out.append(dto)
```

**최소 행 요건**:
- `_compute_zscore_dto` 가 `_Z_WINDOW + 2 = 22` 행 이상 필요
- 따라서 `end_idx = _Z_WINDOW + 1 = 21` (sub 길이 22) 부터 시작

**`collect()` 시그니처 확장**:
```python
async def collect(self, *, backfill: bool = False, period: str | None = None)
```
- `backfill=True` → `collect_macro_history_sync()`
- `backfill=False` (기본) → `collect_sync()` (기존 동작 유지)

**예상 결과**:
- 8 티커 × ~250 거래일(1y) = 최대 2,000 슬라이드
- Z-score 임계값(2.0~2.5) 초과 비율 ~2~5% → **40~100건** 예상

---

### 2. Yahoo Backfill CLI — `scripts/yahoo_backfill.py`

```bash
# Finance + Macro 둘 다 (기본)
cd backend && python scripts/yahoo_backfill.py --mode all

# Finance만, 6개월
python scripts/yahoo_backfill.py --mode finance --period 6mo

# Macro만, 1년
python scripts/yahoo_backfill.py --mode macro --period 1y
```

**argparse 옵션**:

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--mode` | `all` | `finance` / `macro` / `all` |
| `--period` | `None`(→ 1y) | yfinance period 문자열 |

---

### 3. 벤처스퀘어 수집기 — `venturesquare_collector.py`

**Platum 완전 동일 패턴, RSS URL / source_type 네임스페이스만 변경**:

| 항목 | Platum | Venturesquare |
|------|--------|--------------|
| RSS URL | `platum.kr/archives/category/funding/feed` | `venturesquare.net/category/funding/feed` |
| source_type 기본 | `PLATUM_INVEST` | `VSQUARE_INVEST` |
| M&A | `PLATUM_MA` | `VSQUARE_MA` |
| IPO | `PLATUM_IPO` | `VSQUARE_IPO` |
| 펀드 | `PLATUM_FUND` | `VSQUARE_FUND` |

**공유 유틸리티**:
- `_rss_investment_krw.extract_investment_amount_krw()` — KRW 금액 추출
- `rss_wordpress_sync.fetch_html_sync()` / `wordpress_main_text()` — 본문 보완 크롤링
- 투자 키워드 필터, 제목 기반 투자자 추출 — Platum과 동일 로직

---

## 🗂️ 최종 Bronze 경제 소스 현황

| 소스 | 컬렉터 | 라우터 | 스케줄러 |
|------|--------|--------|---------|
| DART | `dart_collector.py` | `POST /bronze/economic/dart` | ✅ 일별 |
| Wowtale RSS | `wowtale_collector.py` | `POST /bronze/economic/wowtale` | ✅ 일별 |
| Wowtale Archive | `wowtale_archive_crawler.py` | `POST /bronze/economic/wowtale-archive` | 수동(Backfill) |
| Platum | `platum_collector.py` | `POST /bronze/economic/platum` | ✅ 일별 |
| **벤처스퀘어** | `venturesquare_collector.py` | `POST /bronze/economic/venturesquare` | 추가 필요 |
| StartupRecipe | `startup_recipe_collector.py` | `POST /bronze/economic/startup-recipe` | ✅ 일별 |
| Yahoo Finance | `yahoo_finance_collector.py` | `POST /bronze/economic/yahoo-finance` | ✅ 일별 |
| Yahoo Finance BF | (위 컬렉터 backfill=True) | `?backfill=true` | 수동(Backfill) |
| Yahoo Macro | `yahoo_macro_collector.py` | `POST /bronze/economic/yahoo-macro` | ✅ 주별 |
| **Yahoo Macro BF** | (위 컬렉터 backfill=True) | `POST /bronze/economic/yahoo-macro-backfill` | 수동(Backfill) |
| ALIO | `alio_public_inst_project_collector.py` | `POST /bronze/economic/alio` | ✅ 주별 |
| MSIT 보도자료 | `msit_bbs_collector.py` | `POST /bronze/economic/msit-press` | ✅ 주별 |
| MSIT 사업공고 | `msit_bbs_collector.py` | `POST /bronze/economic/msit-biz` | ✅ 주별 |
| MSIT R&D 예산 | `msit_publicinfo_63_collector.py` | `POST /bronze/economic/msit-rnd-budget` | ✅ 월별 |
| MOEF PDF | `moef_local_pdf_collector.py` | `POST /bronze/economic/moef-upload` | 수동 업로드 |

---

## 🚀 운영 가이드

### 벤처스퀘어 스케줄러 등록 (권장)

`core/scheduler.py` 의 일별 잡 목록에 추가:
```python
await svc.ingest_venturesquare(max_items=50, fetch_article_if_short=True)
```

### Yahoo Macro Backfill 1회 실행

```bash
# 서버에서 직접 실행 (DB 연결 필요)
cd backend
python scripts/yahoo_backfill.py --mode macro --period 1y
```

또는 API로 트리거:
```bash
curl -X POST http://localhost:8000/master/bronze/economic/yahoo-macro-backfill
```

### Yahoo Finance Backfill 1회 실행

```bash
python scripts/yahoo_backfill.py --mode finance --period 1y
```

또는:
```bash
curl -X POST "http://localhost:8000/master/bronze/economic/yahoo-finance?backfill=true"
```

---

## 🔗 관련 문서

- `WOWTALE_YAHOO_ENHANCEMENT_STRATEGY.md`: 전체 전략 원문
- `WOWTALE_ARCHIVE_CRAWLER_IMPL.md`: Phase 1D 구현 기록
- `BRONZE_ARCHITECTURE_DECISION.md`: Bronze 계층 전체 설계
