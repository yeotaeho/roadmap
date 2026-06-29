# Master Domain Documents

## Core

- `economic/README.md`: 경제 도메인 문서 인덱스
- `economic/core/MASTER_BRONZE_IMPLEMENTATION_STATUS.md`: 현재 구현 상태 SSOT
- `economic/core/BRONZE_ARCHITECTURE_DECISION.md`: Bronze 아키텍처 결정
- `economic/core/DATA_COLLECTION_STRATEGY.md`: 공통 수집 전략
- `economic/core/RAW_ECONOMIC_DATA_COLLECTION_GUIDE.md`: 경제 데이터 수집 가이드
- `economic/core/ECONOMIC_DATA_SOURCE_STATUS.md`: 데이터 소스 제약과 이력
- `economic/core/ECONOMIC_FLOW_IMPLEMENTATION_ROADMAP.md`: 경제 흐름 구현 로드맵
- `economic/core/COLLECTOR_EXPANSION_REVIEW.md`: 컬렉터 확장 검토

## Source Domains

- `economic/government/`: ALIO 및 정부 문서
- `economic/dart/`: DART 수집 전략
- `economic/opportunity/`: 사업 공고와 Opportunity 수집
- `economic/startup_media/`: 스타트업 미디어, The VC, Wowtale
- `economic/market/`: Yahoo Finance 및 시장 데이터

## Bronze 4축 확장 (2026-06-24, 마이그레이션 e2c5a7b9d3f4)

`raw_economic_data` 외 4개 흐름 축의 수집 전략. 소스 주소·키·함정 카탈로그는 [`backend/docs/sources/`](../../../docs/sources/README.md).

- [`people/PEOPLE_COLLECTION_STRATEGY.md`](people/PEOPLE_COLLECTION_STRATEGY.md): 사람·역량(Competency)·채용 수요(Demand) — `raw_people_data`
- [`discourse/DISCOURSE_COLLECTION_STRATEGY.md`](discourse/DISCOURSE_COLLECTION_STRATEGY.md): 뉴스·담론(이슈·리스크) — `raw_discourse_data`(신규)
- [`opportunity/OPPORTUNITY_COLLECTION_STRATEGY.md`](opportunity/OPPORTUNITY_COLLECTION_STRATEGY.md): 기회·지원(K-Startup·나라장터) — `raw_opportunity_data`
- [`company/COMPANY_MASTER_COLLECTION_STRATEGY.md`](company/COMPANY_MASTER_COLLECTION_STRATEGY.md): 검증 기업 마스터 — `verified_company_master`(신규)

### 공통 인프라 메모
- **대량 적재 배치(asyncpg 32,767 파라미터 한도)**: 모든 Bronze repository의 insert/upsert는 `BaseRepository._commit_batched_returning`(1000행/배치)을 사용한다. 벤처명단 39k·KIAT 11k 등 대량 수집 시 필수.
- **한국 공공 API 검증 원칙**: 합성 파싱 테스트는 실제 응답과 다를 수 있으므로, 키 없이라도 1회 live 호출로 엔드포인트·필드·등급제한을 확인한다(영문 페이지 `/en/data/<id>/openapi.do`가 End Point를 더 잘 노출).
