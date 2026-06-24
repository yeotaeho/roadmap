# Bronze 데이터 소스 카탈로그

도메인별 외부 수집 소스 기록. 각 행: 소스 · 엔드포인트 · 데이터 · source_type · 키 · 상태.
상태 범례 — ✅ 구현 / 🟡 골격(키 게이트, 차기 완성) / 📄 문서(차기 후보).

| 도메인 | 파일 | Bronze 테이블 |
|---|---|---|
| 사람·역량/수요 | [people_sources.md](people_sources.md) | `raw_people_data` |
| 담론·이슈/리스크 | [discourse_sources.md](discourse_sources.md) | `raw_discourse_data` |
| 기회·지원 | [opportunity_sources.md](opportunity_sources.md) | `raw_opportunity_data` |
| 검증 기업 마스터 | [company_master_sources.md](company_master_sources.md) | `verified_company_master` |

> Economic·Innovation 소스는 상위 [DATA_COLLECTION_SOURCES_GUIDE_V3.md](../DATA_COLLECTION_SOURCES_GUIDE_V3.md) · [INNOVATION_AND_PEOPLE_PIPELINE_CODEX_GUIDE.md](../INNOVATION_AND_PEOPLE_PIPELINE_CODEX_GUIDE.md) 참조.

## 한국 공공 API 공통 함정 (메모리 교훈)

- **합성 파싱 테스트 ≠ 실제 API**: 키 없이라도 live 1회 호출로 실제 응답 포맷 확인 필수.
- **data.go.kr 4대 함정**: xmltodict List/Dict · 날짜 필드 혼동 · HTML/CDATA 원형 보존 · source_url NOT NULL Fallback.
- **RSS 시간대**: feedparser `*_parsed`는 UTC → `calendar.timegm` 사용(`time.mktime` 금지, KST 9h 오차).
- **data.go.kr 키 재사용**: 계정당 동일 인코딩키 → `DATA_GO_KR_SERVICE_KEY` 하나로 다수 서비스 폴백.
