# ALIO 공공기관 사업정보 수집 전략

> **라우팅 정정 (2026-05-13 이후)**  
> 본 API(`15125286`)는 초기에 Opportunity(`raw_opportunity_data`)로 연결되었으나, **`DATA_COLLECTION_SOURCES_GUIDE_V3.md` 기준으로 Economic(`raw_economic_data`)가 정답**임을 확인하여 **경제 버킷으로 이관**하였다.  
> 사용자 액션(신청·접수)이 아닌 **공공기관이 예산을 받아 운영하는 사업의 메타정보**이며, 기재부 예산안·과기부 R&D 예산과 같은 **「돈의 흐름」** 신호로 분류한다.  
> 엔드포인트: `POST /api/master/bronze/economic/alio` (구 `/bronze/opportunity/alio` 폐기).

> **작성일**: 2026-05-13  
> **API 승인일**: 2026-05-13  
> **목적**: data.go.kr ALIO 공공기관 사업정보 OpenAPI(`15125286`)로 300여 공공기관의 **사업·프로그램 메타**를 수집하여 `raw_economic_data`에 적재하고, 거시 예산·집행 분석·타 소스와의 교차검증에 활용한다.

---

## 🎯 핵심 결정 사항

**결정**: ALIO API는 **`raw_economic_data`에만 적재**한다. (Grant/Opportunity Primary 아님.)

| 항목 | 값 |
|------|-----|
| **API 분류** | Government program metadata — **기관 집행 예산·사업 단위 자본 흐름** |
| **Target 테이블** | `raw_economic_data` (Primary) |
| **Bronze DTO** | `EconomicCollectDto` |
| **Collector 경로** | `hub/services/collectors/economic/alio_public_inst_project_collector.py` |
| **Ingest 서비스** | `BronzeEconomicIngestService.ingest_alio_projects()` |
| **수집 주기** | **주 1~2회** (연·분기 단위 갱신이 중심, 실시간성 낮음) |
| **필터링** | **키워드 화이트리스트** + **기관 화이트리스트**(기본 9개 기관; `inst_filter=[]`면 전 기관) |
| **중복 방지** | `raw_economic_data`의 `source_url` **UNIQUE** + Repository `insert_many_skip_duplicates` |
| **보완재** | **KONEPS(`3073756`)** — ALIO는 사업 메타·거시 예산, KONEPS는 **입찰·실행(사용자 액션 가능)** → Opportunity Primary 유지 |

**근거 (V3 가이드와 동일 논리)**  
> **ALIO 기반 사업정보는 공공기관이 정부 예산을 받아 운영하는 사업 그 자체의 메타정보**이다. 사용자 액션(신청·접수) ❌, 조회만 ⭕. 기재부 예산안·과기부 R&D 예산과 **같은 결의 돈의 흐름** 신호이다.

**핵심 철학**: ALIO는 **프로그램·예산 레이어(거시·메타)** , KONEPS는 **입찰·계약 레이어(미시·실행)**. Silver에서 `source_type`·테이블을 분리해 조인·교차 분석한다.

---

## 📊 API 개요

### 공식 정보

| 항목 | 내용 |
|------|------|
| **공식명** | 공공기관 사업정보 조회 서비스 |
| **API ID** | `15125286` |
| **제공기관** | ALIO(공공기관 경영정보 공개 시스템) — 기획재정부 산하 |
| **포털** | `https://www.data.go.kr/data/15125286/openapi.do` |
| **Base URL (승인 화면·명세)** | `https://apis.data.go.kr/1051000/biz` |
| **목록 API (구현값)** | `GET https://apis.data.go.kr/1051000/biz/list` (`AlioPublicInstProjectCollector.BASE_URL`) |
| **코드 정의서 (PDF)** | `MOEF_NKOD_DB_05_코드 정의서_v1.2` — `bizClsf`, `lifecyclLst`, `instClsf`, `instType`, `srvcClsf` 등 **쿼리·응답 코드** 정의 (청년 일자리 올인원 NKOD) |
| **인증** | Open API 키 — `.env`의 `ALIO_SERVICE_KEY` 또는 `ALIO_API_KEY` (`settings.alio_service_key`). 포털 안내: **인코딩/디코딩 키** 중 환경에 맞는 쪽을 시도 |
| **응답** | 명세상 `resultType` 기본 **json**; Collector는 `resultType=json` 고정 후 JSON·레거시 XML 래퍼 모두 파싱 시도 |
| **호출 제한** | 일일 한도는 승인 메일·포털 기준 준수(통상 1,000건 전후 가정) |
| **범위** | 전국 약 300여 공공기관의 사업·프로그램 기본 정보 |

### 요청 파라미터 (명세·승인 화면 기준)

| 파라미터 | Collector 사용 | 설명 |
|---------|----------------|------|
| `serviceKey` | ✅ | 인증키 |
| `pageNo` | ✅ | 페이지 |
| `numOfRows` | ✅ | 페이지당 건수(최대 `max_items`와 100 중 작은 값) |
| `resultType` | ✅ | `json` 고정(명세 기본값과 동일) |
| `bizNm` | (추후) | 사업명 부분 검색 — 서버 필터로 쓰면 클라이언트 키워드 부하 감소 |
| `bizClsf` | (추후) | 세부사업분류 — **PDF `BIZ_CLSF` 코드** (예: `B020104` 정보화지원) |
| `instCd` | (추후) | 행정표준 기관코드 — 기관정보 API·PDF `INST` 계열과 조합 |
| `instClsf` / `instType` | (추후) | 기관 분류·유형 — **PDF 기관정보코드분류** |
| `lifecyclLst` | (추후) | 생애주기(복수는 콤마) — **PDF `LIFE_CYCLE`** (예: `03` 청년) |
| `srvcClsf` | (추후) | 편의서비스 분류 — PDF 참조 |

**제거됨**: 구현에 있던 `bizYear` 쿼리 파라미터는 본 명세 목록에 없어 **전송하지 않음**. 연도 필터는 응답 필드·제목 등 **클라이언트**에서 유지한다.

### PDF(`MOEF_NKOD_DB_05`) 활용 방법

1. **API 요청 필터를 좁힐 때**: 명세 이미지에 “코드 정의서 첨부 참고”로 나온 파라미터(`bizClsf`, `lifecyclLst`, …)의 **허용 값**을 PDF에서 찾아 쿼리에 넣는다. 예: 청년 대상만 보고 싶으면 `lifecyclLst=03` (PDF 3.3절 `LIFE_CYCLE`).
2. **응답 해석·Silver 태깅**: JSON의 `bizClsfNm` 등 이름 필드와 함께, 원본 코드가 오면 PDF로 **의미 있는 한글 카테고리**로 매핑한다.
3. **기관 단위 집계**: `instCd`를 쓸 경우 공공기관 기본정보 API(`15125287`)와 PDF `INST` 코드를 맞춘 뒤 조인한다.

### 응답 스키마(가이드용)

- **NKOD JSON**: 최상위 `resultCode`(정상 `0`/`200` 등, 오류 시 `7` 게이트웨이 인증 등) + `result` 배열(또는 `result` 객체 내 `list` 등). 항목 예: `bizNm`, `bizExpln`, `instNm`, `bizClsfNm`, `siteUrl`, `lifecyclNmList`, `bizPeriodExpln` (명세 이미지 예시).
- **레거시 XML/JSON 래퍼**: `response.header.resultCode` = `00` 계열 → `body.items.item[]` — 구형 게이트웨이 호환용으로 Collector가 병행 처리한다.

실제 필드명은 기관·시점별로 변형될 수 있으므로 **`scripts/alio_probe.py`로 1차 확인**한다. Collector는 `bizNm`/`bizName` 등 **다중 후보 필드**에서 `_pick`으로 흡수한다.

---

## 🎁 데이터 특성 및 활용

### 데이터 정체

- 공공기관이 **정부 예산을 집행해 운영하는 사업**의 메타데이터(명칭, 기관, 예산 규모, 기간, 담당 등).
- **지원 신청 UI·접수 마감을 대체하지 않는다.** (그 역할은 SMES 사업공고, 각 기관 사이트, KONEPS 입찰 등이 담당.)
- **「돈의 흐름」**: 사업 단위 예산(`budgetKrw`)은 MOEF 거시 예산안·MSIT R&D 예산 HWPX와 **같은 분석 축**에 둔다.

### 1차 활용: `raw_economic_data` (Primary)

**대상 사용자**: 정책·리서치·내부 거시 대시보드, Silver에서 기관·연도·분야별 집계.

**Use case 예시**

- 2026년 **공공기관 R&D 성격 사업** 예산 총액·기관별 분포 (`GOVT_ALIO_RND` 등 `source_type` 필터).
- AI·데이터·스타트업 키워드와 연계한 **분야별 공공 집행 규모** 추이.
- 동일 기관에 대해 **KONEPS 입찰 금액**과 비교해 실행률·프로그램 대비 입찰 전환 시그널 탐색.

**Silver 처리 힌트**

- `investment_amount`·`currency=KRW`로 집계 가능한 금액 축 확보.
- `raw_metadata.original_item`에 원본 dict 보존 → 스키마 변화에도 재파싱 여지.
- `raw_metadata.biz_target` 등은 **정책 분류용 텍스트**로 쓰되, Opportunity의 “지원 대상 엔티티”와 혼동하지 않는다.

### 차별점: KONEPS(나라장터)와의 관계

| 항목 | ALIO `15125286` → **`raw_economic_data`** | KONEPS `3073756` → **`raw_opportunity_data`** (Primary) |
|------|---------------------------------------------|--------------------------------------------------------|
| **정체** | 기관이 운영하는 **사업·프로그램 메타** | **입찰 공고**·계약 실행 축 |
| **시간 단위** | 연·분기 중심 | 일·주 단위 공고·마감 |
| **사용자 의도** | “어디에 얼마가 잡혀 있나” (거시) | “이 입찰에 참여할까” (액션) |
| **예산** | 사업 총예산(`budgetKrw`) | 건별 예정가격·낙찰가 |
| **교차** | 기관명·연도·키워드로 KONEPS와 **조인 가설** 생성 | 실행·입찰 증빙 |

**보완 시나리오 (요약)**  
ALIO에서 “○○원 AI 바우처 사업(예산 50억)”을 포착 → Silver에서 동일 기관의 KONEPS 용역·물품 입찰을 시간창으로 묶어 “프로그램 대비 실행 파이프라인”을 설명한다.

---

## 📡 수집 전략

### 주기·운영

| 단계 | 주기 | 방법 |
|------|------|------|
| 개발·검증 | 수동 | `python scripts/alio_probe.py`, `python scripts/alio_integration_test.py` |
| API 검증 | 수동 | `POST /api/master/bronze/economic/alio` (curl·Postman) |
| 운영 | 주 1~2회 | 스케줄러(별도)에서 동일 엔드포인트 또는 서비스 메서드 호출 |

### 전수 vs 필터

300여 기관 × 다수 사업으로 **RAW 폭주** 가능 → 기본값은 **기관 9곳 + 키워드 OR**.  
운영·디버그 시 `inst_filter=[]` 및 `disable_keyword_filter=true`로 완화할 수 있다(라우터 쿼리 파라미터).

### 증분·중복

이상적: API가 `updDtFrom` 등을 지원하면 서버측 증분.  
현실: **전량 재수집 + `source_url` 유일성**으로 멱등 적재가 단순하고 안전하다. Repository 층에서 스킵 카운트를 반환한다.

---

## 🗂️ 데이터 스키마 (DTO → Bronze)

### Collector 출력: `EconomicCollectDto`

**정의**: `backend/domain/master/models/transfer/economic_collect_dto.py`

| DTO 필드 | ALIO 매핑 | 비고 |
|----------|-----------|------|
| `source_type` | 제목 기반 분류 | `GOVT_ALIO_PROJECT`(기본), `GOVT_ALIO_RND`, `GOVT_ALIO_STARTUP`, `GOVT_ALIO_SME` |
| `source_url` | `detailUrl` 등 → 없으면 `job.alio.go.kr/businessdetail.do?bizId=` → 최후 `https://www.alio.go.kr/` | NOT NULL에 가깝게 항상 문자열 확보 |
| `raw_title` | `bizNm` 계열 | 최대 500자 |
| `investor_name` | `instNm` 계열 | **예산 집행 주체(공공기관)** 를 “투자 주체” 슬롯에 매핑, max 255 |
| `target_company_or_fund` | — | **항상 `None`** (`bizTarget`은 의미 혼동 방지를 위해 `raw_metadata`만) |
| `investment_amount` | `budgetKrw` 파싱 | 정수 원화; 없으면 `None` |
| `currency` | `"KRW"` | 고정 |
| `published_at` | `regDt`/`updDt` 등 KST 파싱 | 가능한 첫 유효값 |
| `raw_metadata` | 아래 키 + `original_item` | 마감 계열 날짜는 DTO 필드 없음 → `deadline` ISO 문자열 |

**`raw_metadata` 표준 키 (ALIO)**

- `biz_id`, `biz_target`, `biz_period`, `category`, `contact_dept`, `contact_tel`, `detail_url`, `biz_year`, `budget_krw`(금액 중복 보존), `original_item`  
- 선택: `deadline` (API에 마감류 필드가 있을 때만)

### Bronze 테이블: `raw_economic_data`

**모델**: `backend/domain/master/models/bases/raw_economic_data.py`

| 컬럼 | 설명 |
|------|------|
| `source_type` | `GOVT_ALIO_*` |
| `source_url` | UNIQUE 제약 (`uq_raw_economic_data_source_url`) |
| `raw_title`, `investor_name`, `target_company_or_fund` | 위 매핑 |
| `investment_amount`, `currency` | 원화 규모 |
| `published_at`, `collected_at` | 시각 |
| `raw_metadata` | JSONB |

---

## 🔧 구현 맵 (실제 코드 기준)

```
backend/
├── domain/master/hub/services/collectors/economic/
│   └── alio_public_inst_project_collector.py   # AlioPublicInstProjectCollector
├── domain/master/hub/services/
│   └── bronze_economic_ingest_service.py       # ingest_alio_projects()
├── api/v1/master/
│   └── master_routor.py                        # POST /bronze/economic/alio
├── core/config/settings.py                     # alio_service_key
└── scripts/
    ├── alio_probe.py
    └── alio_integration_test.py
```

### Collector 요약

- **클래스**: `AlioPublicInstProjectCollector(service_key)`  
- **비동기**: `collect(max_items=, inst_filter=, biz_year=, disable_keyword_filter=)` → `list[EconomicCollectDto]`  
- **동기**: `collect_sync(...)` (테스트·스크립트 편의)  
- **페이지네이션**: `numOfRows` ≤ 100, `max_items` 충족까지 `pageNo` 증가  
- **견고성**: xmltodict 실패 시 JSON 시도; `item` 단일 dict/list 정규화; API resultCode 비정상 시 빈 리스트.

### 서비스·응답 형태

`BronzeEconomicIngestService.ingest_alio_projects(...)` 반환 예:

```json
{
  "source": "alio_projects",
  "fetched": 87,
  "inserted": 40,
  "not_inserted": 47
}
```

---

## 🌐 API (FastAPI)

**메서드**: `POST /api/master/bronze/economic/alio`  
(`main.py`의 `API_V1_PREFIX=/api` + 라우터 `prefix=/master`)

**쿼리 파라미터**

| 이름 | 기본 | 설명 |
|------|------|------|
| `max_items` | 200 | 1~2000 |
| `inst_filter` | 생략 시 기본 9기관 | 다중 쿼리; `[]` 전달 시 전 기관 |
| `biz_year` | null | 2020~2030 |
| `disable_keyword_filter` | false | true 시 키워드 필터 해제 |

**curl 예시**

```bash
curl -X POST "http://localhost:8000/api/master/bronze/economic/alio?max_items=100&biz_year=2026&disable_keyword_filter=false"
```

**에러**

- `ALIO_SERVICE_KEY` 미설정 → 400 (`ValueError` 메시지)  
- 수집 중 예외 → 502

---

## 🔗 KONEPS와의 통합·SQL 예시 (버킷 분리 반영)

### 시나리오: 기관 단위 “예산(ALIO) vs 입찰(KONEPS)”

```sql
-- (1) ALIO 경제 메타: 한 기관·연도 AI 관련 사업 예산 합
SELECT COALESCE(SUM(investment_amount), 0) AS budget_krw_sum, COUNT(*) AS n
FROM raw_economic_data
WHERE source_type LIKE 'GOVT_ALIO%'
  AND investor_name LIKE '%한국산업기술진흥원%'
  AND published_at >= TIMESTAMPTZ '2026-01-01'
  AND raw_title ILIKE '%AI%';

-- (2) KONEPS(가정: raw_opportunity_data 적재 시) 동일 기관 입찰
SELECT COUNT(*) AS bids, COALESCE(SUM(investment_amount), 0) AS bid_amount_sum
FROM raw_opportunity_data
WHERE source_type LIKE 'KONEPS%'
  AND investor_name LIKE '%한국산업기술진흥원%'
  AND published_at >= TIMESTAMPTZ '2026-01-01'
  AND raw_title ILIKE '%AI%';
```

Silver에서는 위 두 쿼리 결과를 **동일 차원이 아님**을 라벨링(“사업 총예산” vs “입찰 건별 금액”)하고, 기관·분야·분기 버킷으로 정렬해 리포트한다.

---

## 📈 향후 확장

1. **NTIS·과제 DB**: ALIO `GOVT_ALIO_RND`와 실제 과제 ID 매칭(별도 키 필요).  
2. **기관 자체 OpenAPI**: ALIO는 광·얕게, 중진공·창진원 등은 깊게 보강.  
3. **LLM Silver**: `raw_metadata`의 목적·대상 텍스트를 산업 태그로 구조화(본 Bronze 문서 범위 밖).  
4. **지역 태그**: 기관 주소·지역 코드가 메타에 붙으면 지역 스타트업 정책 맵과 결합.

---

## ⚠️ 주의 사항

- **Rate limit**: 일일 호출·`numOfRows`·주기 운영으로 분산.  
- **스키마 변화**: `_pick` 다중 필드·`original_item` 보존으로 완화.  
- **타임존**: `published_at`/`deadline` 파싱은 KST 기준으로 맞춘 뒤 DB는 timestamptz 저장.  
- **정책**: 공공데이터 **이용약관·재배포 제한** 준수.  
- **보안**: 서비스 키는 서버 환경변수만; 클라이언트에 내리지 않음.

---

## 📚 참고

| 항목 | 위치 |
|------|------|
| 소스 분류 기준 | `backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md` |
| 정부 문서 크롤 패턴 | `GOVT_DOCS_COLLECTION_STRATEGY.md` |
| SMES(OpenAPI 패턴 유사) | `SMES_OPENAPI_COLLECTION_GUIDE.md` |
| ALIO 포털 | https://www.data.go.kr/data/15125286/openapi.do |

---

## ✅ 운영 체크리스트

### 환경

- [ ] `.env`에 `ALIO_SERVICE_KEY`(또는 `ALIO_API_KEY`) 설정  
- [ ] 백엔드 기동 후 `alio_probe`로 응답 구조 스팟 체크(필드명 변동 모니터링)

### 기능

- [ ] `ingest_alio_projects`가 키 미설정 시 명확히 실패하는지  
- [ ] 기본 화이트리스트·키워드 필터 ON 상태에서 건수·품질 샘플링  
- [ ] `disable_keyword_filter=true`·`inst_filter=[]` 조합으로 스모크  
- [ ] `source_url` 중복 재적재 시 `not_inserted` 증가 확인

### 데이터 품질

- [ ] `GOVT_ALIO_*` 분포가 제목 키워드와 대체로 일치하는지  
- [ ] `investment_amount` NULL 비율(원문에 예산 없는 케이스) 기록  
- [ ] KONEPS 적재 후 기관명 정규화 이슈(별칭) 정리 백로그

---

## 심화: 거시 분석 시나리오 라이브러리 (Economic 관점)

이 절은 **동일 데이터(ALIO)를 Silver·리포트에서 어떻게 읽을지**에 대한 시나리오 묶음이다. SQL은 Postgres 가정 예시이며, 실제 컬럼·인덱스는 마이그레이션을 따른다.

### 시나리오 1 — 연도·기관 매트릭스

**질문**: 2026년에 화이트리스트 9개 기관이 각각 잡고 있는 AI·데이터 관련 사업 예산 합은?  
**접근**: `source_type LIKE 'GOVT_ALIO%'` AND `raw_title`/`raw_metadata` 텍스트에 키워드 AND `published_at` 연도 필터.  
**주의**: `published_at` NULL 행은 `biz_year` 메타로 보조 필터하거나 제외 정책을 문서화한다.

### 시나리오 2 — R&D 라벨만 추출

**질문**: `GOVT_ALIO_RND`만 모아서 분기별 신규 건수 추이는?  
**접근**: `source_type = 'GOVT_ALIO_RND'`로 1차 집계 후, `collected_at`이 아닌 **`published_at`** 기준으로 비즈니스 시계열을 만든다(Bronze 수집 시각과 혼동 금지).

### 시나리오 3 — 예산 NULL 비율 모니터링

**질문**: 얼마나 많은 사업이 예산 금액 없이 올라오는가?  
**SQL 힌트**: `COUNT(*) FILTER (WHERE investment_amount IS NULL)` / 전체 건수.  
**조치**: NULL 비율이 급등하면 API 스키마에서 예산 필드명이 바뀌었을 가능성을 1순위로 본다.

### 시나리오 4 — 기관명 퍼지 매칭

**질문**: 사용자가 "산업기술진흥원"처럼 짧게 쳤을 때 KIAT 전체를 잡으려면?  
**접근**: Silver에서 기관 정규화 테이블을 두고 `investor_name`을 canonical id로 매핑. ALIO 원문은 `raw_metadata.original_item.instNm`에 남는다.

### 시나리오 5 — 중복 URL 재적재율

**질문**: 주 2회 배치가 정상인지 어떻게 알까?  
**접근**: 두 번 연속 실행 후 `inserted`≈0, `not_inserted`≈`fetched`에 수렴해야 정상이다. 급격한 `inserted` 재상승은 **신규 사업 공표** 또는 **source_url 생성 규칙 변경**을 의심한다.

### 시나리오 6 — 키워드 필터 민감도

**질문**: "디지털"만으로 너무 넓게 잡힌다면?  
**접근**: (1) 키워드 리스트를 코드에서 조정, (2) Silver에서 2차 제외, (3) 일시적으로 `disable_keyword_filter`로 RAW 샘플링 후 리스트 재조정.

### 시나리오 7 — `GOVT_ALIO_SME` vs 실제 중소기업 지원

**질문**: 제목에 "중소기업"만 있고 실제로는 대기업 행사인 경우?  
**접근**: 휴리스틱 한계를 문서화하고 Silver LLM/룰에서 `biz_target`·`biz_purpose`를 읽어 재라벨.

### 시나리오 8 — 스타트업 특화 뷰

**질문**: 스타트업 팀에게 보여줄 "공공 R&D·창업 레일" 대시보드 쿼리 초안은?  
**접근**: `source_type IN ('GOVT_ALIO_STARTUP','GOVT_ALIO_RND')` AND 투자 금액 상위 N, 기관별 파이 차트.

### 시나리오 9 — MOEF·MSIT 문서와의 정합

**질문**: 동일 연도에 MSIT HWPX에서 나온 총액과 ALIO 합계를 비교하면?  
**접근**: 둘은 **집계 단위가 다름**(부처 총괄 vs 기관별 사업 라인아이템). 리포트에서는 "비교 불가"가 아니라 **서로 다른 레벨의 교차검증**으로 서술한다.

### 시나리오 10 — KONEPS와의 시간 정렬

**질문**: ALIO 사업 시작 분기와 KONEPS 첫 입찰 공고 사이의 리드 타임 분포는?  
**접근**: 기관 키 정규화 후 `published_at` 차이 히스토그램. NULL·이상치는 별도 버킷.

### 시나리오 11 — 지역 정책(향후)

**질문**: 지자체 출연 기관이 ALIO에 잡히면?  
**접근**: `investor_name`에 지역 키워드가 포함되는 경우가 많다 → Silver 지역 태그 1차 룰.

### 시나리오 12 — 감사 추적

**질문**: 왜 이 row가 생겼는지 감사팀에 설명하려면?  
**접근**: `collected_at`, `raw_metadata.original_item`, 호출 파라미터 로그(운영에서만, PII 주의).

### 시나리오 13 — 장애 복구

**질문**: 하루치 수집이 빈 결과로 떨어졌다면?  
**접근**: API 장애 vs 필터 과다 vs 키 만료를 순서대로 분리 진단(부록 C와 연계).

### 시나리오 14 — 비용 상한

**질문**: 월간 최대 호출 수를 넘지 않게 하려면?  
**접근**: `max_items` 상한을 운영 등급별로 다르게 두고, 스테이징은 소량만.

### 시나리오 15 — 다중 환경

**질문**: 스테이징 DB에만 FULL 수집하고 프로덕션은 화이트리스트만?  
**접근**: 환경변수로 `inst_filter` 기본값을 바꾸지 말고, **호출 파라미터**를 배치 설정으로 분리하는 편이 명확하다.

### 시나리오 16 — 데이터 품질 SLI

**제안 지표**: (a) 파싱 실패율 로그 카운트, (b) `investment_amount` NULL 비율, (c) `source_url`이 fallback base 비율(품질 저하 신호).

### 시나리오 17 — 제목 기반 분류 오분류 샘플링

**질문**: `GOVT_ALIO_SME`인데 실제는 대기업 R&D인 경우?  
**접근**: 주간 랜덤 샘플 20건을 리뷰 큐에 넣는 운영 프로세스.

### 시나리오 18 — API 응답 속도

**질문**: 페이지가 느리면?  
**접근**: 타임아웃 45초 내에서 실패하면 해당 페이지만 중단하고 지금까지 수집분 반환(현 구현은 break).

### 시나리오 19 — JSON 응답으로 전환 시

**질문**: 포털이 JSON을 기본으로 바꾸면?  
**접근**: Collector는 이미 JSON 폴백 파싱을 포함 — 다만 `items` 래핑 차이를 Probe로 재확인.

### 시나리오 20 — 법무 검토 포인트

**질문**: 크롤이 아니라 OpenAPI인데도 주의할 점은?  
**접근**: **2차 가공물의 라이선스**·서비스 약관상 **재판매 제한** 여부를 법무에 확인.

---

## 심화: 단계별 운영 플레이북 (Phase 세분화)

### Phase 0 — 사전 준비

계정 승인, 키 발급, `.env` 배선, 스테이징 DB에 `raw_economic_data` 마이그레이션 존재 확인, 방화벽 아웃바운드 허용.

### Phase 1 — 연결성

`alio_probe`로 HTTP 200 및 `resultCode` 정상 확인. 첫 `item` 키 목록을 위키에 스냅샷.

### Phase 2 — 샘플 적재

`max_items=20`, 기본 필터로 `economic/alio` 호출 → DB 20행 확인 → `source_url` UNIQUE 위반 없는지.

### Phase 3 — 필터 튜닝

키워드/기관 조합별 건수·대표 제목을 스프레드시트로 기록. 비즈니스가 수용 가능한 커버리지인지 합의.

### Phase 4 — 배치 승격

스케줄러에 등록. 실패 알림 채널 연결. 롤백 절차(해당 `source_type`만 purge) 문서화.

### Phase 5 — Silver 합류

집계 테이블·뷰 생성. KONEPS 스테이징과 조인 PoC.

### Phase 6 — 지속 개선

월간 리뷰: 필드 변화, NULL 비율, 분류 오류 샘플.

---

## 심화: FAQ

**Q1. 왜 Opportunity가 아닌가?**  
A. 본 API는 신청 액션이 아니라 **기관이 운영 중인 사업 카드**이며 V3 가이드에서 Economic으로 규정한다.

**Q2. `target_company_or_fund`에 `bizTarget`을 넣지 않는 이유는?**  
A. DTO 의미가 "투자 대상 기업·펀드"인데 ALIO의 지원 대상 텍스트는 정책 구분용으로 해석이 달라 **오해 소지**가 크다.

**Q3. 마감일이 꼭 필요하면?**  
A. `raw_metadata.deadline`을 사용하거나 Silver에서 기관 사이트를 재조회한다.

**Q4. SMES와 중복인가?**  
A. 중소부 **사업공고**와 ALIO **기관 사업 메타**는 출처·액션성이 다르다. 둘 다 존재해도 된다.

**Q5. DART 키 없이 Economic 서비스를 만들 수 있나?**  
A. `BronzeEconomicIngestService(db, None, alio_key)` 형태로 dart 없이 ALIO만 주입 가능하다.

---

## 심화: SQL 스니펫 추가 모음

```sql
-- 투자 금액 상위 50건 (메타 품질 확인용)
SELECT source_type, investor_name, investment_amount, raw_title
FROM raw_economic_data
WHERE source_type LIKE 'GOVT_ALIO%'
ORDER BY investment_amount DESC NULLS LAST
LIMIT 50;

-- 기관별 건수·예산 합
SELECT investor_name,
       COUNT(*) AS n,
       SUM(investment_amount) AS sum_amt
FROM raw_economic_data
WHERE source_type LIKE 'GOVT_ALIO%'
GROUP BY 1
ORDER BY sum_amt DESC NULLS LAST;
```

---

## 심화: 코딩 컨벤션 (본 구현과의 정합)

- Collector 파일명은 economic 폴더의 다른 수집기와 같이 **역할이 드러나게** 길게 유지한다.  
- 서비스 메서드명은 `ingest_<source>` 패턴을 따른다(`ingest_alio_projects`).  
- 라우터 경로는 kebab-case (`/bronze/economic/alio`).  
- 로그 prefix는 `Bronze economic ALIO`로 통일해 검색 용이성을 확보한다.

---

## 심화: 보안·컴플라이언스 체크리스트 (확장)

- [ ] API 키가 Git에 커밋되지 않았는지  
- [ ] 프로덕션 로그에 `serviceKey`가 남지 않도록 HTTP 로깅 필터  
- [ ] GDPR/국내 개인정보보호법 관점에서 연락처 컬럼 노출 범위 검토  
- [ ] 장애 시 사용자 메시지에 내부 stack trace 미노출

---

## 심화: 데이터 사전 (비기술 이해관계자용)

| 한글 표현 | 의미 |
|-----------|------|
| 사업 예산 | 해당 연도·사업 단위로 **잡혀 있는 돈의 규모**(집행 완료 아님) |
| 기관 | 예산을 **운용하는 주체** |
| ALIO | 여러 기관의 사업 카드를 **한 API로 묶어 보여 주는 창구** |

---

## 심화: 알려진 한계

- 제목 키워드 기반 `source_type`은 **정답 라벨이 아니다**.  
- 일부 사업은 예산 필드가 비어 있거나 문자열 형식이 비표준일 수 있다.  
- `detailUrl`이 없을 때 생성하는 `job.alio.go.kr` 링크가 항상 200을 보장하지는 않는다(기관 정책).

---

## 심화: 타 시스템 ID와의 매핑 전략(향후)

내부 `program_id`를 발급하고 `(investor_name, biz_id, biz_year)` 복합키를 자연키 후보로 삼되, 기관별 `biz_id` 체계가 변할 수 있으므로 **버전 컬럼**을 Silver에서 관리하는 방안을 검토한다.

---

## 심화: 리허설 체크 (릴리즈 전)

1. 스테이징에서 `max_items=2000` 스트레스(네트워크 안전 시에만).  
2. DB 커넥션 풀 고갈 여부 관찰.  
3. 실패 시 재시도 정책이 트랜잭션을 꼬이지 않는지 확인.

---

## 부록 A — `source_type` 분류 규칙(구현 일치)

| 조건(제목 부분문자) | `source_type` |
|---------------------|----------------|
| `R&D` / `연구개발` / `기술개발` | `GOVT_ALIO_RND` |
| `창업` / `스타트업` / `예비창업` | `GOVT_ALIO_STARTUP` |
| `중소기업` / `소상공인` | `GOVT_ALIO_SME` |
| 그 외 | `GOVT_ALIO_PROJECT` |

---

## 부록 B — 모니터링 쿼리 예시

```sql
-- 최근 적재 20건
SELECT id, source_type, investor_name, investment_amount, left(raw_title, 80), published_at
FROM raw_economic_data
WHERE source_type LIKE 'GOVT_ALIO%'
ORDER BY collected_at DESC
LIMIT 20;

-- source_type별 건수
SELECT source_type, COUNT(*)
FROM raw_economic_data
WHERE source_type LIKE 'GOVT_ALIO%'
GROUP BY 1
ORDER BY 2 DESC;
```

---

## 부록 C — 장애 시나리오 플레이북(요약)

| 증상 | 우선 조치 |
|------|-----------|
| HTTP 401/403 | 키 인코딩·만료·승인 상태 확인 |
| `resultCode` 비정상 | 포털 공지·IP 제한·점검 시간대 확인 |
| 파싱 0건 | `alio_probe`로 본문 앞부분 저장 후 필드명 변화 대응 |
| 삽입 0·fetch 양수 | 대부분 필터에 걸림 → `disable_keyword_filter`/기관 필터 완화 테스트 |

---

## 부록 D — Phase 로드맵(문서·구현 정합)

| Phase | 내용 | 상태 |
|-------|------|------|
| 1 | Probe·필드 맵 확정 | `scripts/alio_probe.py` |
| 2 | Collector·DTO·중복 정책 | `alio_public_inst_project_collector.py` |
| 3 | Economic 서비스·라우터 | `ingest_alio_projects` + `POST .../economic/alio` |
| 4 | 스케줄러·알림 | 인프라별 별도 설계 |
| 5 | Silver·KONEPS 조인 | 도메인별 후속 |

---

## 부록 E — 원본 API 필드와 `_pick` 후보 목록(개발자용)

| 용도 | 후보 필드 tuple (순서대로 탐색) |
|------|----------------------------------|
| 제목 | `bizNm`, `bizName`, `projectNm`, `title` |
| 기관 | `instNm`, `insttNm`, `orgNm`, `instName` |
| 목적(키워드 필터) | `bizPurpose`, `purpose`, `bizCn`, `description` |
| 사업 ID | `bizId`, `bizNo`, `projectId`, `projectSeq` |
| 상세 URL | `detailUrl`, `dtlUrl`, `linkUrl`, `url` |
| 예산 | `budgetKrw`, `budget`, `bizBudget`, `totBudget` |
| 연도 | `bizYear`, `year`, `bizYy` |
| 마감 | `deadlineDt`, `closeDt`, `applEndDt`, `reqstEndDt` → metadata `deadline` |

---

## 부록 F — 운영 파라미터 튜닝 가이드

| 목표 | 권장 |
|------|------|
| 비용 절감 | `max_items` 낮추기, `biz_year` 지정, 기본 기관 화이트리스트 유지 |
| 커버리지 확대 | `inst_filter`에 기관 추가 또는 빈 리스트로 전체 허용 |
| 노이즈 허용 실험 | `disable_keyword_filter=true` (운영 장기 사용은 비권장) |

---

## 부록 G — Silver 레이어에서의 해석 가이드

- `investment_amount`는 **사업 총예산**으로 해석하고, KONEPS 금액과 **직접 비교하지 말 것**(정의가 다름).  
- `investor_name`은 **집행 기관**이며 VC·기업 투자자가 아니다.  
- `GOVT_ALIO_STARTUP` 등 라벨은 키워드 휴리스틱이므로 Silver에서 재분류 가능.

---

## 부록 H — 샘플 `raw_metadata` (축약)

```json
{
  "biz_id": "…",
  "biz_target": "중소기업, 스타트업",
  "biz_period": "2026.03~2026.12",
  "category": "AI",
  "contact_dept": "…",
  "contact_tel": "…",
  "detail_url": "https://…",
  "biz_year": "2026",
  "budget_krw": 5000000000,
  "deadline": "2026-06-30T00:00:00+09:00",
  "original_item": { }
}
```

---

## 부록 I — 데이터 거버넌스

- **출처 표시**: UI·리포트에 ALIO·적재 시각 명시.  
- **보존 기간**: 회사 정책에 따른 Bronze 보존·파기 규칙 적용.  
- **PII**: 연락처는 공개 정보이나 불필요 시 Silver 이전에 마스킹 검토.

---

## 부록 J — 성능·배치

- 한 호출당 최대 페이지 수 ≈ `ceil(max_items / 100)` — 상한 2000이면 최대 약 20회 HTTP.  
- 동시 스케줄 잡이 겹치지 않도록 **분산 락** 또는 **단일 리더** 권장.

---

## 부록 K — 테스트 매트릭스(수동)

| 케이스 | 기대 |
|--------|------|
| 키 없음 | 400 + 안내 메시지 |
| 기본 파라미터 | 삽입≥0, `source`=`alio_projects` |
| `biz_year=2099` | 빈 결과 또는 소량(데이터 의존) |
| 동일 요청 2회 | `inserted`↓, `not_inserted`↑ |

---

## 부록 L — 용어집

| 용어 | 의미 |
|------|------|
| ALIO | 공공기관 경영정보 공개 시스템 |
| 사업 메타 | 신청서가 아니라 **사업 카드** 수준의 정보 |
| 돈의 흐름 | 예산 배정·집행 축의 신호 (Economic) |

---

## 부록 M — 이전 Opportunity 라우팅과의 차이

| 항목 | 이전 | 현재 |
|------|------|------|
| 테이블 | `raw_opportunity_data` | `raw_economic_data` |
| DTO | `OpportunityCollectDto` | `EconomicCollectDto` |
| 엔드포인트 | `POST .../opportunity/alio` | `POST .../economic/alio` |
| 마감 | `deadline_at` 컬럼 | `raw_metadata.deadline` |
| 기관명 | `host_name` 등 Opportunity 필드 | `investor_name` |

---

## 부록 N — 스케줄 예시 (의사 코드)

```text
월·목 09:05 KST: POST /api/master/bronze/economic/alio?max_items=500
실패 시: 지수 백오프 3회, 슬랙 웹훅(선택)
```

---

## 부록 O — 로그에서 확인할 키워드

- `Bronze economic ALIO projects ingest`  
- `ALIO API 페이지 N 호출 실패`  
- `ALIO 아이템 파싱 실패`

---

## 📝 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-05-13 | 초안 — Opportunity 중심 |
| 2026-05-13 | **Economic 버킷 이관**, DTO·라우터·문서 전면 정합 |

---

**문서 끝.** 구현 변경 시 본 문서의 경로·필드 표를 동기화한다.
