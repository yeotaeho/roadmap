# Opportunity 소스 카탈로그 — raw_opportunity_data (기회/지원)

> 기회 흐름. 채용·부트캠프·공모전·정부지원사업 등 사용자에게 '기회'가 되는 공고.
> 상태: ✅ 구현 / 🟡 골격(키 게이트) / 📄 문서(차기 후보).
> 조사·검증일 2026-06-23.

## 구현·후보 소스

| 소스 | 엔드포인트 | 데이터 | source_type | 키 | 상태 |
|---|---|---|---|---|---|
| 중기부 사업공고 | `apis.data.go.kr/1421000/mssBizService_v2/getbizList_v2` | 정부 지원사업 | `SMES_*` | `SMES_SERVICE_KEY` | ✅(기존) |
| K-Startup 통합공고 | `apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01` · [data.go.kr/15125364](https://www.data.go.kr/data/15125364/openapi.do) | 정부 창업지원 공고(GRANT) | `OPP_KSTARTUP_GRANT` | `KSTARTUP_SERVICE_KEY` (data.go.kr) | ✅ **live검증** |
| 나라장터 입찰공고 | `apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc` · [data.go.kr/15129394](https://www.data.go.kr/data/15129394/openapi.do) | 정부→민간 입찰(거시 자본) | `OPP_G2B_BID` | `NARAJANGTEO_SERVICE_KEY` | ✅ **live검증** |
| 공모전(위비티·링커리어·캠퍼스픽) | wevity.com · linkareer.com · campuspick.com | 공모전/대외활동(CONTEST) | — | 불필요(크롤링) | 📄 |
| ALIO 공공기관 채용 | [data.go.kr/15125273](https://www.data.go.kr) | 공공기관 채용(JOB) | — | `ALIO_SERVICE_KEY` | 📄 |
| HRD-Net K-Digital Training | work24 | 국가 부트캠프(BOOTCAMP) | — | `HRDNET_API_KEY` | 📄 |

## 구현 메모 / 함정 (data.go.kr 4대 함정)

1. **xmltodict List/Dict 혼동** → `_ensure_list()`(smes_collector) 재사용. K-Startup·나라장터 컬렉터가 import.
2. **날짜 필드 혼동**: 등록일 ≠ 게시일 ≠ 모집시작. K-Startup은 `pbanc_rcpt_bgng_dt`→published, `pbanc_rcpt_end_dt`→deadline.
3. **HTML/CDATA 원형 보존**: `raw_content`에 공고 본문 원형 그대로(정제는 Silver).
4. **source_url NOT NULL Fallback**: 정상 URL → 공고ID 조합(`pbancSn`/`bidNtceNo`) → 기관 홈.
- **응답 형식**: K-Startup은 신형 `{"data":[...]}`(odcloud)과 구형 `response.body.items.item` 둘 다 처리하도록 `extract_items` 관대화. (2026-06-24 live 확인: `apis.data.go.kr/B552735` 호스트가 정답, nidapi는 SSL오류.)
- **나라장터 필수값(2026-06-24 live)**: `inqryDiv=1`(공고게시일시) + `inqryBgnDt`/`inqryEndDt`(YYYYMMDDHHMM) 없으면 `resultCode 08 "필수값 입력 에러"`. 컬렉터가 `days_back`(기본30)으로 기간 자동계산.
- **키 재사용**: data.go.kr 계열은 계정당 동일 인코딩키 → `DATA_GO_KR_SERVICE_KEY` 하나로 K-Startup/나라장터 폴백 가능(settings AliasChoices).
- **수집기**: `collectors/opportunity/kstartup/kstartup_collector.py` (✅), `collectors/opportunity/narajangteo/narajangteo_collector.py` (🟡).
