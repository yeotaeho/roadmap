# 빈약 섹터 Bronze 소스 보강 제안 (조사·설계)

> 작성 2026-06-25. Pulse 12섹터 중 **7개가 신호 빈약**(전 구간 중립 50)으로 진단됨. 근본 원인은 수집 소스가 기술·금융·바이오·에너지·식품에 쏠려 나머지 섹터에 신호를 거의 안 만든다는 것. 본 문서는 그 7개 섹터에 닿을 신규/확장 Bronze 소스 후보를 조사·우선순위화한다. 기존 소스 SSOT: [DATA_COLLECTION_SOURCES_GUIDE_V3.md](./DATA_COLLECTION_SOURCES_GUIDE_V3.md).

## 0. 대상 섹터 (data_status=insufficient, 2026-06-25 실측)
fintech, mobility, content-creator, edutech, beauty-fashion, logistics, social-service. (active 5개: ai-data, semiconductor, bio-health, energy-climate, food-agri.)

## 1. 평가 기준
1인 개발 수집 가능 · 공개/오픈 API 우선(ToS-clean) · 선행지표 가치 · **섹터 귀속이 명확**(강제 매핑=날조 금지, 기존 원칙) · 기존 수집기 패턴 재사용 가능성.

## 2. 두 갈래 — 확장(싼 것) vs 신규(부처 보도자료)

### 2-A. 기존 수집기 확장 — 최소 코드, 즉효 (먼저 권장)
이미 도는 수집기에 섹터 커버리지만 늘리는 것. 신규 collector 불필요.

| 대상 섹터 | 확장 | 근거 | 작업량 |
|---|---|---|---|
| fintech·mobility·content·edutech | **KIPRIS 키워드군 수율 audit** | 가이드 §2: KIPRIS는 이미 핀테크·모빌리티·콘텐츠·에듀테크 키워드군 보유. 그런데 Pulse는 빈약 → 수율 부족 or 섹터 매핑 누락 의심. 실수율·`sector_source_map(tech_category)` 매핑 점검 후 키워드/IPC 보강. | 소 |
| beauty-fashion | **관세 수출 `customs_group`에 화장품·패션 카테고리 추가** | 혁신축 customs 수집기(`INNOVATION_CUSTOMS_EXPORT`)가 이미 동작. K-뷰티/패션 수출은 강한 선행 신호. `sector_source_map(customs_group→beauty-fashion)` 시드만 추가. | 소 |
| fintech·mobility | **Yahoo 시장 티커에 금융·모빌리티 ETF/종목 추가** | `_MARKET_SOURCE_MAP`은 현재 AI·반도체·바이오 티커만. KODEX 은행·2차전지/모빌리티 ETF 등 추가 → market 축 신호 발생. | 소 |

> 이 3건은 **기존 collector·매핑 시드 확장**이라 가장 싸고, fintech·mobility·beauty를 가장 빨리 살린다. 다만 KIPRIS audit은 실수율 확인(prod 읽기)이 선행돼야 정확.

### 2-B. 신규 부처 보도자료 수집기 — 기존 BS4 증분 패턴 재사용
`msit_bbs_collector`·`mfds_bbs_collector`·`mss_bbs_collector`가 검증한 **BS4 증분 크롤 패턴**을 그대로 복제. 가이드 §1-C에 이미 P0/P1로 식별된 것들이 빈약 섹터와 정확히 대응.

| 대상 섹터 | 신규 소스 | source_type | 축 | 패턴 | feasibility | 우선 |
|---|---|---|---|---|---|---|
| content-creator | **KOCCA 한국콘텐츠진흥원** 보도자료·콘텐츠산업 통계·지원사업 | `GOVT_KOCCA_*` | economic/opportunity | MSIT BS4 + data.go.kr | 높음 (가이드 §1-C P0) | **P0** |
| social-service | **보건복지부(MOHW)** 보도자료 + Subsidy24 복지 분류 매핑 | `GOVT_MOHW_*` | economic/opportunity | MSS BS4 + 기존 Subsidy24 | 높음 | **P0** |
| mobility | **국토교통부(MOLIT)** 보도자료·자동차 등록 통계 | `GOVT_MOLIT_*` | economic/people | BS4 + data.go.kr | 높음 | P1 |
| fintech | **금융위(FSC)** 보도자료 | `GOVT_FSC_POLICY` | economic(정책) | MSS BS4 | 높음 (가이드 §1-C P1) | P1 |
| edutech | **교육부(MOE)** 보도자료·에듀테크 정책 | `GOVT_MOE_*` | economic | BS4 | 중~높음 | P2 |
| logistics | **국토부/해수부 물류·항만 물동량** + 나라장터(KONEPS) 물류 입찰 | `LOGI_*` / `KONEPS_*` | economic/opportunity | data.go.kr + KONEPS API(가이드 §5 P1) | 중 | P2 |

> feasibility "높음"은 **기존 유사 collector가 존재**(BS4 증분·data.go.kr·Subsidy24)함을 근거로 한 패턴-검증 수준이다. 각 소스의 실제 게시판 구조·API 키·데이터 양은 **구현 1단계에서 검증** 필요(아직 미검증).

## 3. 권장 시퀀스
1. **2-A 확장 3건 먼저** (KIPRIS audit·customs 뷰티·시장 ETF) — 최소 코드로 fintech·mobility·beauty 즉시 개선. KIPRIS audit은 prod 수율 확인이 선행.
2. **2-B 중 KOCCA·MOHW(P0)** — content-creator·social-service에 신규 신호 공급. BS4 패턴 복제.
3. 나머지(MOLIT·FSC·MOE·물류)는 효과 측정 후 순차.

각 소스는 단일 수직(collector→`raw_*`→`sector_source_map`/`_SECTOR_CODE_MAP` 매핑→Pulse 반영)으로, **선정 후 개별 spec→plan→구현 사이클**을 따른다.

## 4. 주의 / 비범위
- **섹터 강제 매핑 금지**: 광범위 지수·다섹터 소스는 단일 섹터로 귀속하지 않는다(기존 SPY/QQQ 제외 원칙과 동일).
- **백필 실행은 별도**: 신규 소스 구현 후 prod 수집·정제 잡 실행은 prod 쓰기 + 외부 API/LLM 비용 = 운영 작업으로 분리(사용자 트리거/승인).
- **ToS·접근 제약**: KVIC·KOTRA(SPA)·네이버 금융(ToS)·크런치베이스(유료)는 회피(기존 결정 유지).
- 본 문서는 후보·우선순위 제안까지다. 실제 API 가용성·게시판 구조 검증과 collector 구현은 다음 단계.
