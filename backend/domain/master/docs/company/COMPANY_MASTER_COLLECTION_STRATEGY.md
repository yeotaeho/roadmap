# 기업 마스터 수집 전략 — verified_company_master

> Bronze 테이블: `verified_company_master` (신규, 마이그레이션 `e2c5a7b9d3f4`) · 도메인: 인사이트를 실제 기업 엔티티에 묶는 검증 축
> 최종 갱신: 2026-06-24

## 1. 목적

정부 인증·선정 기업 명단을 마스터로 적재해, 다른 신호(투자·특허·채용)를 **실제 기업**에 연결할 검증 기반을 만든다. ERD source_type: `KSTARTUP_PREUNICORN / VENTURE_CERTIFIED / INNOBIZ / MAINBIZ`.

## 2. 신규 테이블·인프라

이번에 0에서 신설.
- 모델: `domain/master/models/bases/verified_company_master.py` (company_name·business_number·corp_number·ceo_name·certification_*·industry_sector·source_file_version 등). **부분 UNIQUE** `(source_type, business_number) WHERE business_number IS NOT NULL`.
- DTO `models/transfer/company_master_dto.py` · Repository `hub/repositories/company_master_repository.py` · Ingest `hub/services/bronze_company_ingest_service.py`.

## 3. 수집기 현황

| 소스 | 컬렉터 | source_type | 키 | 상태 |
|---|---|---|---|---|
| **중기부 벤처기업명단** | `company/venture_list/venture_list_collector.py` | `VENTURE_CERTIFIED` | VENTURE_LIST_SERVICE_KEY | ✅ live검증 |
| DART 기업개황(보강) | `company/dart_overview/dart_overview_collector.py` | `DART_COMPANY_OVERVIEW` | DART_API_KEY | 🟡 골격 |

엔드포인트(2026-06-24 live): `api.odcloud.kr/api/15084581/v1/uddi:47b202c9-f0bb-43b4-949c-ebe9ef56ef02` (2026-06-01판, 모집단 39,668).

## 4. ⚠️ 설계·실측 함정

### 사업자번호 부재 → 듀얼 UPSERT (핵심)
벤처기업명단 fileData는 **사업자등록번호 컬럼이 없다**(업체명·대표자명(익명)·벤처확인유형·지역·주소·업종명(11차)·벤처유효시작/종료일·벤처확인기관). 따라서 부분 UNIQUE만으로 멱등성이 안 잡힌다. Repository는 **두 경로**로 처리:
- 사업자번호 有 → `ON CONFLICT (source_type, business_number) DO UPDATE`(갱신).
- 사업자번호 無 → `(source_type, company_name)` 기준 신규만 INSERT(재실행 중복 방지).

### 실제 컬럼명 (live로만 확인)
`업종명(11차)`·`업종분류(기보)`·`벤처유효시작일`·`벤처확인기관` 등 — 추정 키와 달라 매핑을 실측에 맞춰 수정. 사업자번호 정규화는 하이픈 제거 후 10자리만 인정.

### odcloud 페이지네이션 상한
**page 11(10,000행)에서 HTTP 400** — odcloud가 1만 행에서 페이지네이션 차단. 전체 39,668 수집은 CSV 다운로드 방식 필요. 컬렉터는 graceful 처리(1만 반환). 현재 9,976행 적재.

### uddi 버전 변경
fileData→OpenAPI 자동변환의 uddi 경로는 **배포(월)마다 변경**. settings `VENTURE_LIST_RESOURCE`(현재 .env에 등록)로 주입, 라우터 `?resource=` override 가능. 미설정 시 컬렉터 `_DEFAULT_RESOURCE` 사용.

## 5. 멱등성·운영
- `company_master_repository.upsert_many`: 듀얼 경로 + 배치(1000행) 헬퍼.
- 라우터 `POST /api/master/bronze/company/venture-list?resource=&file_version=`. 스케줄러 월간.
- 실적재(2026-06-24): VENTURE_CERTIFIED 9,976.

## 6. 차기 (문서만)
DART 기업개황 본구현(corp_code 매핑으로 사업자/법인번호 보강), K-예비유니콘·이노비즈·메인비즈 명단, 국세청 사업자등록 진위확인.

> 소스 카탈로그: [`backend/docs/sources/company_master_sources.md`](../../../../docs/sources/company_master_sources.md)
