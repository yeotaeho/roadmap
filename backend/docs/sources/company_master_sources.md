# Company Master 소스 카탈로그 — verified_company_master

> 정부 인증·선정 기업 마스터. 인사이트를 실제 기업 엔티티에 묶는 검증 축.
> 상태: ✅ 구현 / 🟡 골격 / 📄 문서(차기 후보).
> 조사·검증일 2026-06-23. (신규 테이블 — 마이그레이션 `e2c5a7b9d3f4`)

## 구현·후보 소스

| 소스 | 엔드포인트 | 데이터 | source_type | 키 | 상태 |
|---|---|---|---|---|---|
| 중기부 벤처기업명단 | [data.go.kr/15084581](https://www.data.go.kr/data/15084581/fileData.do) → `api.odcloud.kr/api/15084581/v1/uddi:47b202c9-f0bb-43b4-949c-ebe9ef56ef02` (2026-06-01판, 39,668행) | 업체명·대표자명(익명)·벤처확인유형·지역·주소·업종명(11차)·유효시작/종료일·확인기관 | `VENTURE_CERTIFIED` | `VENTURE_LIST_SERVICE_KEY` (data.go.kr) | ✅ **live검증** |
| DART 기업개황 | [opendart.fss.or.kr/api/company.json](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002) | 사업자/법인번호·대표자·설립일·업종 | `DART_COMPANY_OVERVIEW` | `DART_API_KEY` (기존) | 🟡 골격 |
| 국세청 사업자등록 진위 | [data.go.kr/15081808](https://www.data.go.kr/data/15081808/openapi.do) | 사업자 상태·진위 검증 | — | data.go.kr | 📄 |
| 금융위 기업기본정보 | [data.go.kr/15043184](https://www.data.go.kr/data/15043184/openapi.do) | 기업 기본정보 | — | data.go.kr | 📄 |
| K-예비유니콘·이노비즈·메인비즈 | 정부 공표 CSV | 선정·인증 명단 | `KSTARTUP_PREUNICORN`/`INNOBIZ`/`MAINBIZ` | 불필요/파일 | 📄 |

## 구현 메모 / 함정

- **사업자번호 부재 함정(중요)**: 벤처기업명단 fileData는 **사업자등록번호가 없을 수 있음**(업체명·대표자·지역·업종 위주). 부분 UNIQUE `(source_type, business_number) WHERE business_number IS NOT NULL`만으로는 멱등성 미보장 → Repository **듀얼 전략**:
  - 사업자번호 有 → `ON CONFLICT (source_type, business_number) DO UPDATE`(갱신).
  - 사업자번호 無 → `(source_type, company_name)` 기준 신규만 INSERT(재실행 중복 방지).
- **odcloud uddi**: fileData→OpenAPI 자동변환 엔드포인트의 `uddi:<resource>` 경로는 **배포 버전마다 변경** → 키 발급 후 data.go.kr 상세에서 확인해 `resource`로 주입(`VENTURE_LIST_RESOURCE` env 또는 라우터 쿼리). 미설정 시 수집 스킵.
- **사업자번호 정규화**: 하이픈 제거 후 숫자 10자리만 인정(`_normalize_bizno`), 불일치 시 None.
- **DART 기업개황**: corp_code 단건 조회 → `corpCode.xml`(전체 고유번호) 매핑 선행 필요 → 현재 골격(기존 DART 키 재사용 예정).
- **수집기**: `collectors/company/venture_list/venture_list_collector.py` (✅), `collectors/company/dart_overview/dart_overview_collector.py` (🟡 골격).
