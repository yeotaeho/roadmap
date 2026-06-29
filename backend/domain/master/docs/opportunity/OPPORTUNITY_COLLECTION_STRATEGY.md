# Opportunity 흐름 수집 전략 — 기회·지원(채용·공모전·부트캠프·지원사업)

> Bronze 테이블: `raw_opportunity_data` · 도메인: "청년이 지금 지원할 수 있는 것"
> 최종 갱신: 2026-06-24

## 1. 목적

정부 지원사업·입찰·창업지원 등 **사용자에게 실행 가능한 기회**를 수집한다. ERD source_type: `JOB / BOOTCAMP / CONTEST / GRANT` + `SMES_* / OPP_*`. 마감일(`deadline_at`)은 앱 알림의 핵심.

## 2. 수집기 현황

| 소스 | 컬렉터 | source_type | 데이터 | 키 | 상태 |
|---|---|---|---|---|---|
| 중기부 사업공고 | `opportunity/smes_collector.py` | `SMES_STARTUP/RND/EXPORT/SCALE_UP/GRANT` | 정부 지원사업 | SMES_SERVICE_KEY | ✅(기존) |
| **K-Startup 통합공고** | `opportunity/kstartup/kstartup_collector.py` | `OPP_KSTARTUP_GRANT` | 정부 창업지원 공고 | KSTARTUP_SERVICE_KEY | ✅ live검증 |
| **나라장터 입찰공고** | `opportunity/narajangteo/narajangteo_collector.py` | `OPP_G2B_BID` | 정부→민간 입찰(거시 자본) | NARAJANGTEO_SERVICE_KEY | ✅ live검증 |

엔드포인트(2026-06-24 live 확인):
- K-Startup: `apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01` (응답 `{"data":[...]}`).
- 나라장터: `apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc`.

## 3. data.go.kr 4대 함정 방어 (smes_collector 패턴 재사용)

K-Startup·나라장터 컬렉터는 SMES 컬렉터의 헬퍼(`_ensure_list`·`_parse_date_to_kst`)를 import해 동일 방어를 적용한다.

1. **xmltodict List/Dict 혼동** → `_ensure_list()`로 항상 list 정규화.
2. **날짜 필드 혼동**(등록일≠게시일≠모집시작) → K-Startup은 `pbanc_rcpt_bgng_dt`→published, `pbanc_rcpt_end_dt`→deadline 명시 매핑.
3. **HTML/CDATA 원형 보존** → `raw_content`에 공고 본문 원형 그대로(정제는 Silver).
4. **source_url NOT NULL Fallback** → 정상 URL → 공고ID(`pbancSn`/`bidNtceNo`) 조합 → 기관 홈.

### ⚠️ 나라장터 필수 파라미터 (live로만 드러남)
`getBidPblancListInfoServc`는 `inqryDiv`(조회구분=1) + 조회기간 `inqryBgnDt`/`inqryEndDt`(YYYYMMDDHHMM)가 **없으면 resultCode 08 "필수값 입력 에러"**. 컬렉터가 `days_back`(기본 30)으로 기간을 자동 계산해 주입.

### 응답 형식 관대화
K-Startup `extract_items`는 신형 `{"data":[...]}`(odcloud)과 구형 `response.body.items.item`(XML wrapping)을 둘 다 처리.

## 4. 키 재사용
data.go.kr 계열은 **계정당 동일 인코딩 serviceKey** → settings AliasChoices로 `DATA_GO_KR_SERVICE_KEY` 단일키가 K-Startup/나라장터/벤처명단의 폴백. 단 각 서비스는 data.go.kr에서 "활용신청"(자동승인) 필요.

## 5. 멱등성·운영
- `opportunity_repository.insert_many_skip_duplicates`: source_url UNIQUE + 배치 헬퍼.
- 라우터 `/api/master/bronze/opportunity/{smes,kstartup,narajangteo}`. 스케줄러: K-Startup·SMES=일별, 나라장터=주별.
- 실적재(2026-06-24): SMES 100 + K-Startup 30 + 나라장터 30.

## 6. 차기 (문서만)
청년 직접 기회 — 공모전(위비티·링커리어·캠퍼스픽 크롤링), ALIO 공공기관 채용, HRD-Net K-Digital Training 부트캠프.

> 소스 카탈로그: [`backend/docs/sources/opportunity_sources.md`](../../../../docs/sources/opportunity_sources.md) · 기존 SMES: [`../economic/opportunity/SMES_OPENAPI_COLLECTION_GUIDE.md`](../economic/opportunity/SMES_OPENAPI_COLLECTION_GUIDE.md)
