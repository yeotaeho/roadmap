# Economic Flow 구현 로드맵 — "돈의 흐름" 파악 수준 진단 + 신규 수집처 구현 전략

> **상태: 구현 이력 문서**
>
> 이 문서 앞부분의 “미구현” 진단은 구현 착수 전 스냅샷이다.
> 현재 구현 여부와 운영 계약은
> [`MASTER_BRONZE_IMPLEMENTATION_STATUS.md`](./MASTER_BRONZE_IMPLEMENTATION_STATUS.md)를 따른다.
> 현재 완료된 주요 항목: BOK ECOS, MFDS, 보조금24, DART 정기공시,
> MSS, DART IPO, NPS, Naver DataLab, KIPRIS.
>
> **작성일**: 2026-06-07
> **목적**: 현재 구현된 Economic Bronze 파이프라인이 "돈의 흐름"을 어느 수준까지 파악하는지 정밀 진단하고, `DATA_COLLECTION_SOURCES_GUIDE_V3.md`에 정의됐으나 **미구현된 수집처**를 실제 API 스펙·코드 컨벤션에 맞춰 **어떻게 구현할지** 구체적으로 정의한다.
> **선행 SSOT**: [`BRONZE_ARCHITECTURE_DECISION.md`](./BRONZE_ARCHITECTURE_DECISION.md) · [`ECONOMIC_DATA_SOURCE_STATUS.md`](./ECONOMIC_DATA_SOURCE_STATUS.md) · [`backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md`](../../../../../docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md)
> **이 문서의 위상**: 외부 API 실측과 구현 과정을 보존하는 실행 이력이다.

---

## 📋 0. TL;DR (의사결정자용 요약)

| 질문 | 답 |
|------|-----|
| **지금 돈의 흐름을 얼마나 보나?** | **약 30~35%.** IT/스타트업 섹터의 **민간 뉴스(후행) + 시장 거래량(동행)** 에 편중. 정부→민간 정량 집행, 거시 자금(FDI/통화량), PE/VC 펀드 흐름은 **거의 0%**. |
| **가장 임팩트 큰 한 방은?** | **한국은행 ECOS API.** 난이도 최하 + 현재 0%인 거시 자금 흐름(FDI·M2·금리)을 정형 시계열로 즉시 확보. |
| **V3 가정 중 틀린 것은?** | ① **보조금24** — 금액이 정형 필드가 아니라 `지원내용` **자유 텍스트**에 묻힘(파싱 필요). ② **FSS 사모펀드** — OpenDART로 **결성금액 수집 불가**, KOFIA/금융위 별도 소스 필요. |
| **즉시 착수 가능한 것은?** | **MFDS 보도자료**(완전 정적 HTML, MSIT 패턴 그대로 클론) + **ECOS**(키 발급 즉시) + **DART 정기공시(A)**(기존 DART 자산 재활용). |
| **구현 방식은?** | 모든 신규 소스가 **기존 6파일 수정 패턴**(§6)으로 들어간다. `raw_economic_data` 스키마·repository·DTO는 **변경 없이 재사용**. |

---

## 🔍 1. 현재 "돈의 흐름" 파악 수준 — 정밀 진단

### 1.1 구현된 Economic 소스 (13종 + 시계열 1종)

| 소스 | 컬렉터 | `investment_amount` | 주기 | 데이터 성격 |
|------|--------|:-------------------:|------|------------|
| DART 주요사항보고(B)+지분공시(D) | `dart_collector.py` + `dart_detail_fetcher.py` | ✅ 상세 API 추출 | 일 | 상장사 M&A·증자·시설투자 (확정 이벤트) |
| Wowtale RSS | `wowtale_collector.py` | ⚠️ 본문 정규식(불완전) | 일 | 스타트업 투자 뉴스 |
| Wowtale 아카이브 | `wowtale_archive_crawler.py` | ⚠️ 정규식 | 수동 | 과거 1년 backfill |
| Platum RSS | `platum_collector.py` | ⚠️ 정규식 | 일 | 스타트업 투자 뉴스 |
| 벤처스퀘어 RSS | `venturesquare_collector.py` | ⚠️ 정규식 | 일 | 스타트업 투자 뉴스 |
| 스타트업레시피 RSS | `startup_recipe_collector.py` | ❌ None | 일 | 스타트업 투자 뉴스 |
| Yahoo Volume Surge (16종) | `yahoo_finance_collector.py` | ✅ volume×VWAP 근사 | 주 | ETF/주식 거래량 급증 신호 |
| Yahoo Macro (8종) | `yahoo_macro_collector.py` | ❌ None (가격지표) | 주 | 환율·금리·원자재·가상자산 Z-score |
| Yahoo Market TS (16종) | `yahoo_market_timeseries_collector.py` | N/A (별도 테이블) | 일 | 일별 OHLCV 연속 시계열 |
| 과기부 보도자료(mId=307) | `msit_bbs_collector.py` | ❌ None | 일 | R&D 시행계획 정책 신호 |
| 과기부 사업공고(mId=311) | `msit_bbs_collector.py` | ❌ None | 일 | R&D 모집공고 |
| 과기부 R&D예산(mId=63) | `msit_publicinfo_63_collector.py` | ❌ None | 일 | HWPX 예산문서 (텍스트 보존) |
| 기재부 PDF | `moef_local_pdf_collector.py` | ❌ None | 수동 | 예산안·재정운용계획 (텍스트 보존) |
| ALIO 공공기관 사업 | `alio_public_inst_project_collector.py` | ❌ None (API 미제공) | 주 | 공공기관 사업 메타 |

### 1.2 자금 흐름 **방향별** 커버리지

| 흐름 방향 | 커버 소스 | 수준 | 핵심 공백 |
|-----------|----------|:----:|----------|
| **민간→민간 (VC 투자)** | RSS 4종 + DART(B·D) | **40%** | RSS 금액 추출 불완전·비상장 시드 누락, DART는 상장사 한정 |
| **정부→민간 (예산·집행)** | MSIT·ALIO·MOEF | **25%** | `investment_amount` 전부 None — **금액 없는 "제목만" 데이터** |
| **시장 자본 이동 신호** | Yahoo Surge·Macro·TS | **60%** | 흐름은 보이나 **원인(WHY) 미연결** |
| **해외→국내 (FDI)** | Yahoo 환율 일부 | **5%** | BOK ECOS 미구현 → FDI 정량 0 |
| **민간→민간 (PE/사모펀드)** | 없음 | **0%** | 소스 자체 부재 |
| **국내→해외 (해외투자)** | 없음 | **0%** | KOTRA·DART 해외출자 미수집 |

### 1.3 산업 **섹터별** 커버리지

| 섹터 | 커버 | 수준 |
|------|------|:----:|
| IT/AI/SW | MSIT 80건+·Yahoo AI ETF·RSS | ✅ 충분 |
| 스타트업 생태계 | RSS 4종 (금액 불완전) | ⚠️ 부분 |
| 제조/반도체 | DART 시설투자·Yahoo 반도체 ETF | ⚠️ 부분 |
| 바이오/헬스케어 | DART 일부·Yahoo Bio ETF | ❌ 약함 (MFDS·MOHW 미구현) |
| 금융/VC시장 | DART D공시 일부 | ❌ 약함 (FSS·BOK·FSC·KVIC 미구현) |
| 에너지/ESG | Yahoo 원자재 Z-score | ❌ 약함 (ME 미구현) |
| 건설/SOC | 없음 | ❌ 없음 (MOLIT 미구현) |
| 콘텐츠/문화 | 없음 | ❌ 없음 (MCST/KOCCA 미구현) |

### 1.4 **선행성** 진단 — V3 철학과의 역전

```
V3 가이드 철학:  선행 행동 지표 > 후행 결과 지표
현재 실제 비율:
  후행 (공시·뉴스·정책 결과)  ████████████████░░░░  ~70%
  동행 (시장 거래량·환율)      █████░░░░░░░░░░░░░░░░  ~25%
  선행 (정책 예고·허가·금리)   █░░░░░░░░░░░░░░░░░░░░  ~5%
```

→ **선행 신호(BOK 금리 결정, MFDS 신약 허가, MSIT 시행계획)** 가 가장 부족하다. MSIT 보도자료는 선행성이 있으나 **금액 추출이 전무**해 "신호는 있는데 규모를 모르는" 상태.

### 1.5 종합 평가

> **현재 파이프라인 = "IT/스타트업 민간 뉴스(후행) + 시장 거래량(동행)" 관측기.**
> Bronze 수집 성숙도 **3/5**, 분석/집계 **1.5/5** (Silver/Gold 미구현). 진정한 "돈의 흐름 내비게이션"이 되려면 **① 정부→민간 정량 집행, ② 거시 자금 흐름, ③ PE/VC, ④ 비IT 섹터 선행 신호** 4개 축을 채워야 한다.

---

## 🧩 2. 미구현 수집처 전체 목록 (V3 기준)

| 구분 | 소스 | source_type (안) | V3 우선순위 | 적재 |
|------|------|-------------------|:-----------:|------|
| §1 본표 | DART 정기공시(A) — R&D·CAPEX | `DART_RND`, `DART_CAPEX` | P1 | `raw_economic_data` |
| §1 본표 | 한국벤처투자(KVIC) | `GOVT_KVIC_AGG` | P1 | `raw_economic_data` |
| §1-1 정량 | 보조금24 | `GOVT_SUBSIDY24_*` | P1 | `raw_economic_data` |
| §1-1 정량 | 한국은행 ECOS | `BOK_ECOS_*` | P1 | `raw_economic_data` |
| §1-1 정량 | 금감원 사모펀드(PEF) | `FSS_PE_FUND_*` | P1 | `raw_economic_data` |
| §1-2 보조축 | BOK 통화정책 보도자료 | `GOVT_BOK_POLICY` | **P0** | `raw_economic_data` |
| §1-2 보조축 | MFDS 허가 보도자료 | `GOVT_MFDS_APPROVAL` | **P0** | `raw_economic_data` |
| §1-2 보조축 | KOCCA/KHIDI 보도자료 | `GOVT_KOCCA_*`/`GOVT_KHIDI_*` | **P0** | `raw_economic_data` |
| §1-2 보조축 | FSC·FSS·MOTIE·ME·MOHW·MOLIT 보도자료 | `GOVT_*_PRESS` | P1 | `raw_economic_data` |
| §5 교차 | 중기부 선정 결과 API | (Opportunity) | P1 | `raw_opportunity_data`+Silver 교차 |
| §5 교차 | 중기부 집행 현황 API | (Opportunity) | P2 | Economic 보조 |

**Held/Skip (구현 대상 아님)**: NTIS(키 미발급) · The VC(ToS) · 네이버 금융(ToS) · Crunchbase(유료).

---

## 🔬 3. 외부 API 실측 결과 — 신규 수집처 재평가

### 3.1 실측 기반 우선순위 (난이도·가치 종합)

| 순위 | 소스 | 구현 난이도 | 돈의 흐름 기여 | 비고 |
|:----:|------|:-----------:|:--------------:|------|
| **1** | **BOK ECOS API** | ⭐ (하) | 🔥 거시 0%→커버 | 정형 시계열, 키 즉시 발급 |
| **2** | **MFDS 보도자료** | ⭐ (하) | 바이오 선행신호 | 완전 정적 → MSIT 클론 |
| **3** | **DART 정기공시(A)** | ⭐⭐ (중) | R&D·CAPEX 계획 | 기존 DART 자산 재활용 |
| **4** | **보조금24** | ⭐⭐⭐ (중상) | 정부→민간 보조금 | **금액 비정형 → 파싱 필요** |
| **5** | **KVIC (MarketWatch PDF + vcs.go.kr)** | ⭐⭐⭐ (중상) | VC 시장 거시 | PDF 파서 신규 |
| **6** | **BOK/MOTIE 보도자료** | ⭐⭐ (중) | 금융·제조 선행신호 | 목록 JS/WAF → Probe |
| **보류** | **FSS 사모펀드(PEF)** | ⭐⭐⭐⭐ (상) | PE/VC 흐름 | **OpenDART 불가** → 소스 재탐색 |

### 3.2 ⚠️ V3 가정 정정 (중요)

V3 가이드는 §1-1에서 보조금24·BOK ECOS·FSS 사모펀드를 동일한 "금액 명시 정량 소스 P1"로 묶었으나, 실측 결과 **세 소스의 난이도가 크게 다르다.**

1. **보조금24** — V3는 `investment_amount` 채움률 90%+를 기대했으나, 실제 API(data.go.kr `15113968`, 정부24 공공서비스 정보)는 **금액 정형 필드가 없다.** 지원금액은 `지원내용` **자유 텍스트**(예: "연간 60억원 이내", "최대 100억원")에 자연어로 기재 → **목록→상세 2단계 호출 + 정규식/LLM 파싱** 필요. 난이도 P1 중 가장 높음.

2. **FSS 사모펀드(PEF) 결성금액** — V3는 `dis.fss.or.kr`/OpenDART로 받을 수 있다고 가정했으나, **OpenDART OpenAPI는 PEF 결성금액 전용 API를 제공하지 않는다.** 펀드공시(`pblntf_ty=G`) 목록은 받아도 결성금액 등 수치는 원문 문서에만 존재. → **금융투자협회(KOFIA) `dis.kofia.or.kr`** 또는 **금융위/예탁결제원 공공데이터** 별도 조사 필요. **현 단계 Held로 강등** 권고.

3. **BOK ECOS** — V3 가정대로 정형·안정. **오히려 §1-1 중 최우선으로 승격** 권고.

> **결론**: §1-1 정량 3종의 실질 우선순위는 **BOK ECOS(즉시) > 보조금24(파싱 투자) > FSS PEF(소스 재탐색·Held)** 로 재정렬한다.

---

## 🛠️ 4. 소스별 구현 상세 방안

각 소스는 §6의 **공통 6파일 수정 패턴**을 따른다. 아래는 소스 고유의 API 스펙·파싱·`source_type`·금액 처리만 다룬다.

---

### 4.1 🥇 한국은행 ECOS API — `BOK_ECOS_*` (1순위)

**왜**: 현재 0%인 거시 자금 흐름(FDI·통화량·금리)을 정형 시계열로 확보. 선행성 최상위 신호.

| 항목 | 값 |
|------|-----|
| 엔드포인트 | `https://ecos.bok.or.kr/api/StatisticSearch/{인증키}/json/kr/{시작}/{종료}/{통계표코드}/{주기}/{시작일자}/{종료일자}/[{항목코드}]` |
| 보조 API | `StatisticTableList`(통계표 목록), `StatisticItemList`(항목), `KeyStatisticList`(100대 지표) |
| 인증 | ECOS 회원가입 시 자동 발급 인증키 (`ecos.bok.or.kr/api/#/AuthKeyApply`) |
| 응답 | JSON — `StatisticSearch.row[]`, 총건수 `list_total_count` |
| **값 필드** | `DATA_VALUE`(값), `TIME`(시점), `UNIT_NAME`(단위), `STAT_CODE`/`STAT_NAME`, `ITEM_NAME1~4` |
| 페이지 | 경로의 `{시작}/{종료}` 건수 범위 (1회 최대 ~10만건) |
| 한도 | 일 ~100,000회 (Probe로 재확인) |

**구현 포인트**:
- **금액 매핑**: 시계열 값이므로 `investment_amount`에 직접 넣지 않고(통화량은 "흐름"이 아닌 "잔액"), **`raw_metadata`에 `data_value`·`unit_name`·`time` 보존**. FDI(국제수지 직접투자)처럼 "유입액"이 명확한 통계만 선택적으로 `investment_amount`에 매핑.
- **`source_type`**: `BOK_ECOS_FDI`(외국인직접투자), `BOK_ECOS_M2`(광의통화), `BOK_ECOS_BASE_RATE`(기준금리).
- **`source_url`**: ECOS 통계표는 URL이 없으므로 **합성 유니크 키** 생성 — 예: `ecos://{통계표코드}/{항목코드}/{TIME}` (멱등 키, §6-G 참조).
- **`published_at`**: `TIME`을 주기별 포맷(연 `YYYY`, 월 `YYYYMM`, 분기 `YYYYQn`, 일 `YYYYMMDD`)으로 파싱.
- **통계표코드는 하드코딩 금지** — 상수 맵으로 두되 `StatisticTableList`로 1회 검증(Probe). 초기 후보: 기준금리 `722Y001`(추정), M2 `101Y00x` 계열, FDI 국제수지 `301Y...`/`085Y...` 계열 — **모두 Probe 확정 필요**.

**Probe 산출물**: `scripts/bok_ecos_probe.py` — 통계표코드·항목코드·단위·실제 일 한도 확정.

```python
# collectors/economic/bok/bok_ecos_collector.py (스켈레톤)
_KST = timezone(timedelta(hours=9))

# Probe로 확정할 통계표 — (통계표코드, 주기, 항목코드, source_type, amount_매핑여부)
_ECOS_TARGETS: tuple[tuple[str, str, str | None, str, bool], ...] = (
    ("722Y001", "M", None, "BOK_ECOS_BASE_RATE", False),   # 기준금리 (값=%)
    # ("101Y00x", "M", "...", "BOK_ECOS_M2", False),       # 광의통화 (잔액)
    # ("301Y...", "M", "...", "BOK_ECOS_FDI", True),        # FDI 유입 (흐름→amount)
)

class BokEcosCollector:
    BASE = "https://ecos.bok.or.kr/api/StatisticSearch"
    def __init__(self, service_key: str):
        if not service_key or not service_key.strip():
            raise ValueError("BOK ECOS 인증키가 비어 있습니다. BOK_ECOS_API_KEY 를 설정하세요.")
        self._key = service_key.strip()

    async def collect(self, start: str, end: str) -> list[EconomicCollectDto]:
        dtos: list[EconomicCollectDto] = []
        for stat_code, cycle, item, stype, is_flow in _ECOS_TARGETS:
            rows = await self._fetch(stat_code, cycle, start, end, item)  # row[] 반환, 에러 격리
            for r in rows:
                value = self._to_int(r.get("DATA_VALUE"))
                dtos.append(EconomicCollectDto(
                    source_type=stype,
                    source_url=f"ecos://{stat_code}/{r.get('ITEM_CODE1','')}/{r.get('TIME','')}",
                    raw_title=f"{r.get('STAT_NAME','')} {r.get('TIME','')}",
                    investment_amount=(value if is_flow else None),
                    raw_metadata={"data_value": r.get("DATA_VALUE"), "unit_name": r.get("UNIT_NAME"),
                                  "stat_code": stat_code, "item_name1": r.get("ITEM_NAME1"), "original_item": r},
                    published_at=self._parse_time(r.get("TIME"), cycle),
                ))
        return dtos
```

- **스케줄**: 주간(`_WEEKLY_JOBS`) — 거시 통계는 월/분기 갱신이라 일 배치 불필요. backfill은 최초 1회 `start=200001`.

---

### 4.2 🥈 MFDS 보도자료 — `GOVT_MFDS_APPROVAL` (2순위, 즉시 착수)

**왜**: 바이오/헬스케어 선행 신호(신약 허가·임상)가 현재 전무. **완전 정적 HTML**이라 MSIT 패턴을 거의 그대로 클론.

| 항목 | 값 |
|------|-----|
| 목록 | `https://www.mfds.go.kr/brd/m_99/list.do?page={N}` (정적 SSR ✅) |
| 상세 | `https://www.mfds.go.kr/brd/m_99/view.do?seq={NUMBER}` (정적 SSR ✅) |
| 워터마크 키 | `seq` (정수) 또는 등록일 |
| 필터 | 제목 키워드 **리스트**: `["허가", "신약", "임상", "품목허가", "조건부"]` |

**구현 포인트**:
- 기존 `MsitBbsCollector`의 `MSITStaticTableListStrategy`(테이블 행 파싱) + 워터마크 로직을 **재사용**. `msit_bbs_collector.py`를 일반화하거나 `mfds_bbs_collector.py`로 클론.
- MSIT는 단일 `title_keyword`였으나 MFDS는 **키워드 리스트**로 확장(`any(kw in title for kw in KEYWORDS)`).
- `investment_amount=None` (정성 신호). `raw_metadata`에 `body_text`·`is_signal=True`·`signal_priority="P0"`·`industry_sector="BIO"`·`board_key="mfds_m99"`.
- **정량 확장(향후)**: 신약 허가를 정량으로 잡으려면 `nedrug.mfds.go.kr`(의약품안전나라) 품목허가 구조화 데이터 별도 Probe.
- 일 배치(`_DAILY_JOBS`), 키 불필요(`BronzeEconomicIngestService(session, None)`).

---

### 4.3 🥉 DART 정기공시(A) — `DART_RND` / `DART_CAPEX` (3순위)

**왜**: 현재 DART는 주요사항보고(B)·지분공시(D)만 — "이미 결정된" 이벤트. 정기공시(A)는 **향후 3~5년 R&D·CAPEX 계획**(반도체·배터리·바이오 선행 지표). 기존 DART 인증키·`dart_detail_fetcher` 자산을 그대로 활용.

| 단계 | API | 엔드포인트 | 용도 |
|------|-----|-----------|------|
| 1) 대상 기업 | 공시검색 | `/api/list.json?pblntf_ty=A` | 사업·분기·반기보고서 제출사 수집 (`rcept_no` 확보) |
| 2) 재무 추출 | 단일회사 전체 재무제표 | `/api/fnlttSinglAcntAll.json` | `bsns_year`·`reprt_code`·`fs_div`로 전체 계정 조회 |

**구현 포인트 (★주의)**:
- **OpenDART에 "연구개발비"·"CAPEX" 전용 API 없음.** `fnlttSinglAcntAll`의 전체 계정에서 **계정명 매칭**으로 추출:
  - **R&D**: `account_nm`이 `"경상연구개발비"`/`"연구개발비"` 인 행 → `thstrm_amount`.
  - **CAPEX**: 직접 계정 없음 → **현금흐름표(CF) 섹션 `"유형자산의 취득"`** 또는 유형자산 증감으로 산출.
- 계정명이 회사별로 비표준 → `account_id`(표준계정ID) 우선, 키워드 fallback. **매핑 테이블 구축**이 핵심 난이도.
- 금액 필드: `thstrm_amount`(당기), `frmtrm_amount`(전기) — `dart_detail_fetcher._to_int_amount` 재사용.
- `reprt_code`: 11011(사업)/11012(반기)/11013(1Q)/11014(3Q), `fs_div`: CFS(연결)/OFS(별도).
- 한도: OpenDART 공통 20,000건/일, 재무 API 1회 100사.
- 별도 `DartPeriodicCollector` 클래스 신규(기존 `dart_collector.py`와 분리 — 호출 흐름이 list→재무 2단계로 다름).
- 분기 배치(주간 또는 분기 트리거) — 정기공시는 분기 단위 갱신.

---

### 4.4 보조금24 — `GOVT_SUBSIDY24_*` (4순위, 파싱 투자 필요)

**왜**: 정부→기업/개인 보조금 지급 신호(월 ~2,000건+). 단 **금액이 비정형**이라 파싱 파이프라인 선투자 필요.

| 항목 | 값 |
|------|-----|
| 데이터셋 | data.go.kr `15113968` (행정안전부 공공서비스 정보) / 정부24 `api.korea.go.kr` |
| 인증 | data.go.kr `serviceKey` |
| 응답 | odcloud JSON / 정부24 XML |
| **금액** | ❌ 정형 필드 없음 — `지원내용` 자유 텍스트 ("연간 60억원 이내" 등). 목록 API는 `sportFr`(현금/현물/정보) 만 |
| 한도 | 개발계정 ~10,000건/일 |

**구현 포인트**:
- **목록 → 상세 2단계 호출**. 목록(`svcId`·`svcNm`·`jrsdDptAllNm`·`svcPpo`·`sportFr`) → 상세(`지원대상`·`지원내용`·`신청방법`).
- **금액 추출**: `지원내용` 텍스트에서 정규식(`억/만원`, `이내/최대/한도` 처리). 기존 `_rss_investment_krw.py`의 원화 정규식 자산 재활용 + 보조금 특화 패턴 추가. 추출 실패 시 `investment_amount=None`, 원문은 `raw_metadata.support_content_raw` 보존(Silver LLM 재처리 대비).
- `source_type`: `GOVT_SUBSIDY24_CASH`(현금성)/`GOVT_SUBSIDY24_OTHER`(현물·정보), `sportFr` 기준 분류.
- `source_url`: `svcId` 기반 정부24 상세 URL.
- **Probe 필요**: odcloud UDDI 정확 엔드포인트(활용신청 후 마이페이지), 정확한 일 한도.
- 주간 배치.

---

### 4.5 KVIC — `GOVT_KVIC_AGG` (5순위, VC 시장 거시)

**왜**: NTIS Held 상황에서 "한국 VC 시장 전체 규모·추세"(조성·투자·회수) 벤치마크. 개별 라운드가 아닌 **거시 단면**.

**3개 채널 중 정공법 조합**:

| 채널 | 내용 | 평가 |
|------|------|------|
| (1) MarketWatch 분기 PDF | `kvic.or.kr/marketWatch/marketWatch1_1`, 미러 `vcletter.co.kr/fileupload/pdf/{YYYY}_KVIC-{NN}-KR.pdf` | **정량 본체** — 조성·투자·회수 시계열. PDF 파서 신규 |
| (2) vcs.go.kr 투자실적 | `vcs.go.kr/web/portal/statistics/list` | **정적 테이블** — 업종별/지역별(억원). MSIT table 전략 재사용. WAF 헤더 위장 필요 |
| (3) data.go.kr 데이터셋 | 마켓워치 발간현황(`15120263`), 모태펀드 실적 | 보조 색인·단면만 |

**구현 포인트**:
- **1순위 vcs.go.kr 정적 테이블** — 업종별 투자액(`investment_amount`에 억원→원 변환 매핑 가능), 연도별. `source_type=GOVT_KVIC_AGG`. WAF 대응은 `_msit_common.make_async_client`의 위장 UA·ConnectionReset 재시도 재사용.
- **2순위 MarketWatch PDF** — `_doc_parsers.py`(pdfplumber) 확장. 분기 PDF의 조성·투자·회수 표 파싱. `moef_local_pdf_collector` 패턴 참고.
- 둘 다 **Probe 필요**(vcs.go.kr WAF 차단 여부, PDF 신판 직링크 패턴).
- 분기/월 배치.

---

### 4.6 BOK·MOTIE·기타 부처 보도자료 — `GOVT_*_PRESS` (6순위)

**MSIT 패턴 재사용 매트릭스** (조사 실측):

| 소스 | 목록 | 상세 | 워터마크 | 재사용도 | 조치 |
|------|------|------|----------|:--------:|------|
| **MFDS** | 정적 ✅ | 정적 ✅ | `seq` | ✅ 거의 그대로 | §4.2 (즉시) |
| **BOK** | JS/AJAX ⚠️ | 정적 ✅ | `nttId` | 상세✅/목록△ | XHR 직접호출 Probe → 안되면 Playwright. 금리는 ECOS 병행 |
| **MOTIE** | Probe ⚠️ | Probe ⚠️ | `dataSeq`(정수) | 잠정 ✅ | WAF 재시도 클라이언트로 Probe. 구 URL(`/motie/ne/presse`) 폐기, 신 `article/ATCL3f49a5a8c` |
| FSC/ME/MOHW/MOLIT | 미조사 | 미조사 | — | — | P1, 개별 Probe |

**구현 포인트**:
- BOK 목록: `bok.or.kr/portal/bbs/P0000559/list.do` (보드 `P0000559`). 상세는 정적이므로 **목록 행만 XHR로 확보**하면 Playwright 불필요. DevTools로 `selectListData`류 POST 엔드포인트 Probe.
- MOTIE: `dataSeq` 증가 정수 ID → 워터마크 이상적. 정부 WAF ConnectionReset → MSIT util 재시도 로직 재사용.
- 공통: `GovtPressCollector` 범용 크롤러(`BRONZE_ARCHITECTURE_DECISION.md` §614 설계)로 선언적 보드 정의(`source_type`·`industry_sector`·`signal_priority`). `investment_amount=None`, `raw_metadata.data_role="TREND_SIGNAL"`.

---

### 4.7 ❌ FSS 사모펀드(PEF) — Held 강등

- **OpenDART로 결성금액 수집 불가** (펀드공시 목록만, 수치는 원문 문서).
- 대안 소스 **Probe 필요**: ① KOFIA `dis.kofia.or.kr`(펀드 설정·순자산), ② 금융위/예탁결제원 공공데이터.
- **권고**: 대안 소스 존재 확인 전까지 **Held**. MVP 필수 아님.

---

## 🔁 5. 기존 소스 품질 보강 (신규만큼 중요)

신규 수집처 추가와 별개로, 이미 들어오는 데이터의 `investment_amount` 채움률을 올리는 작업이 ROI가 높다.

| 대상 | 현 상태 | 조치 | 난이도 |
|------|---------|------|:------:|
| RSS 4종 (Wowtale/Platum/VS/SR) | 금액 정규식 불완전·SR은 None | `_rss_investment_krw.py` 정규식 강화 + 본문 2-step 크롤링 + SR 금액 추출 추가 | ⭐⭐ |
| ALIO | `investment_amount` 전부 None | API 응답 예산 필드 재Probe (`bizBdgt` 등), 없으면 기관 사업 메타로만 유지 | ⭐ |
| DART (B·D) | Phase 3 미완 | 상세 fetcher 라우트 커버리지 확대 | ⭐⭐ |
| MSIT/MOEF | 텍스트만 보존 | Silver LLM 단계에서 HWPX/PDF 본문 금액 추출 (Bronze 범위 밖) | ⭐⭐⭐ |

---

## 🧱 6. 공통 구현 패턴 — 신규 Collector 추가 체크리스트

> 모든 신규 소스는 **6개 파일**만 건드리면 된다. `raw_economic_data` 스키마·repository·DTO는 **변경 없이 재사용**. 멱등 키는 **`source_url` UNIQUE**.

### 6-A. `EconomicCollectDto` 필드 (변경 없음)
`domain/master/models/transfer/economic_collect_dto.py`

| 필드 | 타입 | 필수 | 비고 |
|------|------|:----:|------|
| `source_type` | str(≤50) | ✅ | 소스/카테고리 키 |
| `source_url` | str? | — | **멱등 유니크 키** (빈값이면 repo가 스킵 → 항상 유효 URL 보장) |
| `raw_title` | str(≤500) | ✅ | 제목 |
| `investor_name` | str?(≤255) | — | 투자/집행 주체 |
| `target_company_or_fund` | str?(≤255) | — | 투자 대상 |
| `investment_amount` | int? | — | 원 단위. 없으면 None |
| `currency` | str(≤10) | — | 기본 "KRW" |
| `raw_metadata` | dict? (JSONB) | — | `original_item` 등 리니지 보존 |
| `published_at` | datetime? | — | KST tz-aware 권장 |
| `collected_at` | datetime | — | repo가 server_default로 채움 |

### 6-B. 신규 파일/수정 6종

| # | 파일 | 작업 |
|---|------|------|
| 1 | `collectors/economic/<src>_collector.py` | **신규** — `__init__` 키검증, `async collect`+`collect_sync`, `_pick` 다중필드, `_fetch_page` 에러격리, `_parse_item`(source_type 분류·유니크 source_url·raw_metadata) |
| 2 | `hub/services/bronze_economic_ingest_service.py` | **수정** — `ingest_<src>` 메서드 + (키 필요시) `__init__` 인자. 반환 `{"source","fetched","inserted","not_inserted",...}` |
| 3 | `api/v1/master/master_routor.py` | **수정** — `POST /master/bronze/economic/<src>`. `ValueError→400`, 외부실패`→502` |
| 4 | `core/config/settings.py` | **수정** — `<src>_service_key: Optional[str]`, `AliasChoices("<SRC>_SERVICE_KEY","<SRC>_API_KEY")` |
| 5 | `core/scheduler.py` | **수정** — `_job_<src>` + `_DAILY_JOBS`/`_WEEKLY_JOBS` 튜플에 한 줄 |
| 6 | `economic_repository.py` / DTO / 모델 | **변경 없음** — 재사용 |

### 6-C. Collector 핵심 규약 (실측 컨벤션)
- `from __future__ import annotations`, `logger = logging.getLogger(__name__)`, `_KST = timezone(timedelta(hours=9))`.
- 키 검증: 빈 키면 `raise ValueError("... 키가 비어 있습니다. <SRC>_SERVICE_KEY 를 설정하세요.")`.
- `_pick(item, fields)` staticmethod로 필드명 변형 흡수.
- `source_type` 분류: DART식 규칙 튜플 `((keyword, stype), ...)` 첫 매칭 + 기본값.
- HTTP API: `aiohttp` 비동기 + `collect_sync` 래퍼. 블로킹 SDK: 동기 작성 후 `asyncio.to_thread`.
- 페이지 루프: 예외는 `break`(부분수집 보존), 아이템 파싱 실패는 `continue`(스킵), `seen_urls`로 배치내 중복 제거.
- `raw_metadata`에 `"original_item": item` 보존(리니지).
- DTO 생성 시 길이 절단(`[:500]`, `[:255]`).

### 6-D. ingest 메서드 표준 반환
```python
result = {"source": "<src>", "fetched": len(dtos), "inserted": inserted,
          "not_inserted": max(0, len(dtos) - inserted)}
logger.info("Bronze economic <SRC> ingest: %s", result)
return result
```

### 6-E. settings 키
```python
bok_ecos_api_key: Optional[str] = Field(
    default=None, validation_alias=AliasChoices("BOK_ECOS_API_KEY", "BOK_ECOS_SERVICE_KEY"))
```

### 6-F. scheduler 등록
```python
async def _job_bok_ecos() -> dict | None:
    settings = get_settings()
    if not settings.bok_ecos_api_key:
        logger.warning("[scheduler] bok_ecos_api_key 없음 — 잡 스킵"); return None
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None, bok_ecos_key=settings.bok_ecos_api_key)
        return await svc.ingest_bok_ecos(start="...", end="...")
# _WEEKLY_JOBS += (("bok_ecos", _job_bok_ecos),)
```

### 6-G. 멱등 키 (가장 중요)
- 중복 방지 SSOT = `UniqueConstraint("source_url", name="uq_raw_economic_data_source_url")`.
- `repo.insert_many_skip_duplicates(dtos)` → `on_conflict_do_nothing(index_elements=["source_url"])`, 실제 insert 행 수 반환.
- **URL 없는 소스(ECOS 등)는 합성 유니크 키 생성**: `ecos://{통계표}/{항목}/{TIME}` 처럼 결정적·유일하게.

---

## 🗺️ 7. 단계별 실행 로드맵

### Phase 0 — 선행 (키 발급 + Probe, ~3일)
| 작업 | 산출물 |
|------|--------|
| ECOS 인증키 발급 + `scripts/bok_ecos_probe.py` | FDI/M2/금리 통계표코드·항목코드 확정 |
| 보조금24 활용신청 + odcloud 엔드포인트 확인 | UDDI 경로·일 한도 |
| BOK 목록 XHR / MOTIE WAF / vcs.go.kr Probe | 정적·동적 판정, Playwright 필요 여부 |
| KOFIA/금융위 PEF 소스 존재 확인 | FSS PEF Held 해제 가능 여부 |

### Phase 1 — 정량 핵심 + 즉시착수 (1~2주)
| 작업 | 축 | 공수 | 완료조건 |
|------|-----|:----:|----------|
| **BOK ECOS Collector** | 거시 정량 | 3일 | FDI/M2/금리 시계열 적재, `source_url` 멱등 |
| **MFDS 보도자료 Collector** | 바이오 선행 | 2일 | MSIT 클론, 키워드 리스트 필터, 일 배치 |
| **RSS 금액 추출 강화 + SR 추가** | 민간 정량 | 2일 | 4종 `investment_amount` 채움률↑ |
| **DART 정기공시(A) Collector** | R&D·CAPEX | 3일 | `fnlttSinglAcntAll` R&D/CAPEX 계정 매핑 |

### Phase 2 — 정부 정량 + VC 거시 (3~4주)
| 작업 | 축 | 공수 |
|------|-----|:----:|
| 보조금24 Collector + 금액 파싱 파이프라인 | 정부→민간 | 4일 |
| KVIC (vcs.go.kr 정적 테이블) | VC 거시 | 3일 |
| KVIC (MarketWatch PDF 파서) | VC 거시 | 3일 |
| `GovtPressCollector` 범용 + BOK·MOTIE | 보조축 선행 | 4일 |

### Phase 3 — 보조축 확장 + 교차분석 (Silver 진입, 1~2개월)
| 작업 | 비고 |
|------|------|
| FSC·ME·MOHW·MOLIT 보도자료 (P1) | `GovtPressCollector` 확장 |
| 중기부 선정 결과 API (Opportunity 교차) | Silver에서 RSS·DART 교차 |
| Silver: 정책 신호 → 자금 집행 시간정렬 Cross-Analysis | "정책→예산→시장" 추적 |
| FSS PEF (대안 소스 확보 시) | Held 해제 조건부 |

---

## 📊 8. 예상 효과 (KPI)

| 지표 | 현재 | Phase 1 후 | Phase 2 후 |
|------|:----:|:----------:|:----------:|
| 돈의 흐름 커버리지 | ~30% | ~50% | ~70% |
| 거시 자금(FDI/M2/금리) | 0% | ✅ 확보 | ✅ |
| 정부→민간 정량 | 25%(금액None) | 30% | 60%(보조금24) |
| 비IT 섹터(바이오/금융) | 약함 | 바이오 선행✅ | 금융·VC✅ |
| 선행 지표 비율 | ~5% | ~20% | ~35% |
| `investment_amount` 채움률 | 낮음 | RSS·DART(A)↑ | 보조금24·KVIC↑ |

**정성 목표**: "이번 분기 바이오에 정부+민간 자금이 얼마나, 어떤 순서로 흘렀나?"(MFDS 허가→DART R&D→RSS 투자), "금리 인상 후 VC 시장이 식었나?"(BOK 금리→KVIC 투자액) 같은 **교차 질문에 정량 답변** 가능.

---

## ⚠️ 9. 리스크 & Probe 필요 항목

| 항목 | 리스크 | 대응 |
|------|--------|------|
| ECOS 통계표코드 | 코드 변경/오선택 | `StatisticTableList` 동적 검증, Probe 확정 |
| 보조금24 금액 | 비정형 텍스트 파싱 정확도 | 정규식+원문보존, Silver LLM 재처리 |
| FSS PEF | OpenDART 불가 | KOFIA/금융위 Probe, 불가 시 Held 유지 |
| BOK/MOTIE 목록 | JS/WAF 차단 | XHR 직접호출 → 안되면 Playwright |
| vcs.go.kr | 웹방화벽 차단 | 위장 UA + ConnectionReset 재시도 |
| 정부 API 키 | 발급 지연/한도 | 개발계정 선발급, 한도 내 페이지네이션 |

**Probe 스크립트 목록**: `bok_ecos_probe.py`, `subsidy24_probe.py`, `bok_bbs_probe.py`, `motie_bbs_probe.py`, `vcs_go_kr_probe.py`, `kofia_pef_probe.py`.

---

## 🔗 10. 관련 문서

- [`backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md`](../../../../../docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md) — 출처 목록 SSOT (§1·§1-1·§1-2·§5)
- [`ECONOMIC_DATA_SOURCE_STATUS.md`](./ECONOMIC_DATA_SOURCE_STATUS.md) — 제약·현황 SSOT
- [`BRONZE_ARCHITECTURE_DECISION.md`](./BRONZE_ARCHITECTURE_DECISION.md) — 6대 정량·22개 부처 매트릭스·`GovtPressCollector` 설계
- [`DART_ECONOMIC_ENHANCEMENT_STRATEGY.md`](../dart/DART_ECONOMIC_ENHANCEMENT_STRATEGY.md) — DART B·D·A 로드맵
- [`GOVT_DOCS_COLLECTION_STRATEGY.md`](../government/GOVT_DOCS_COLLECTION_STRATEGY.md) — 부처 게시판 크롤 패턴·`source_type` 정의
- [`COLLECTOR_EXPANSION_REVIEW.md`](./COLLECTOR_EXPANSION_REVIEW.md) — DART(A)·SMES 확장 검토

---

## ✅ 11. 구현 진행 현황 (2026-06-07 착수)

### 11.1 완료 — MFDS 보도자료 (`GOVT_MFDS_APPROVAL`) ✅ 라이브 검증

| 산출물 | 경로 |
|--------|------|
| Collector | `collectors/economic/mfds/mfds_bbs_collector.py` |
| Service | `bronze_economic_ingest_service.py::ingest_mfds_press` + `_latest_mfds_watermark` |
| Router | `POST /master/bronze/economic/mfds-press` |
| Scheduler | `_job_mfds_press` → `_DAILY_JOBS` (일 09:00 KST) |
| 단위 테스트 | `scripts/economic_new_sources_parse_test.py` (39 PASS) |
| 통합 테스트 | `scripts/mfds_integration_test.py` (라이브+DB, 키 불필요) |

**라이브 Probe 결과 (실측 셀렉터 — 문서의 "정적 SSR" 가정 확정)**:
- 목록 행: `div.bbs_list01 > ul > li` (페이지당 10건, 첨부 `ul.bbs_file_list li` 는 직계자식 `>` 로 제외)
- 제목: `a.title`, href `./view.do?seq={N}&...` → **canonical `view.do?seq={N}` 로 정규화**(멱등 키, 휘발 파라미터 제거)
- 날짜: `div.right_column` = `2026-06-05` (ISO)
- 본문: `div.bv_contents` (제목+첨부 메타 — MFDS 보도자료 본문은 HWPX/PDF 첨부에 존재)
- 스모크: 2페이지 20건 중 키워드(허가/지정/임상) 매칭 4건 정상 적재, 본문 229자 클린 추출

### 11.2 완료(코드) — BOK ECOS (`BOK_ECOS_*`) ⏳ 키 발급 대기

| 산출물 | 경로 |
|--------|------|
| Collector | `collectors/economic/bok/bok_ecos_collector.py` (`_ECOS_TARGETS` — 기준금리 활성, M2/FDI 주석) |
| Service | `bronze_economic_ingest_service.py::ingest_bok_ecos` |
| Router | `POST /master/bronze/economic/bok-ecos` |
| Scheduler | `_job_bok_ecos` → `_WEEKLY_JOBS` (월 09:00 KST, 최근 13개월) |
| settings | `bok_ecos_api_key` (`BOK_ECOS_API_KEY`) |
| 단위 테스트 | 파싱·DTO·키검증 (39 PASS 에 포함) |
| Probe | `scripts/bok_ecos_probe.py` (M2·FDI STAT_CODE 확정용) |
| 통합 테스트 | `scripts/bok_ecos_integration_test.py` (키 없으면 SKIP) |

**활성화 절차(사용자)**: ① `BOK_ECOS_API_KEY` 발급·`.env` 설정 → ② `python scripts/bok_ecos_probe.py` 로 M2/FDI STAT_CODE 확정 → ③ `_ECOS_TARGETS` 주석 해제 → ④ 통합 테스트.

### 11.3 settings 키 placeholder 추가
- `bok_ecos_api_key` (`BOK_ECOS_API_KEY` / `BOK_ECOS_SERVICE_KEY`)
- `subsidy24_service_key` (`SUBSIDY24_SERVICE_KEY` / `SUBSIDY24_API_KEY`) — 보조금24 구현 시 사용

### 11.4 다음 착수 후보
- 보조금24 Collector (키 발급 후, `지원내용` 텍스트 금액 파싱)
- DART 정기공시(A) `DartPeriodicCollector` (기존 DART 키 재사용, `fnlttSinglAcntAll` R&D/CAPEX)
- KVIC (vcs.go.kr 정적 테이블 + MarketWatch PDF)

---

## 📝 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-06-07 | 초안 — 현황 진단 + 미구현 7종 구현 방안. 외부 API 실측으로 V3 §1-1 정정(보조금24 비정형/FSS PEF 불가), 우선순위 재정렬(ECOS 최우선) |
| 2026-06-07 | §11 구현 착수 — MFDS Collector 라이브 검증 완료, BOK ECOS 코드 완성(키 대기), settings 키 placeholder, 단위 39 PASS |
