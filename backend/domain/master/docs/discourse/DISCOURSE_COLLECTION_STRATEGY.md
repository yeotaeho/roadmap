# Discourse 흐름 수집 전략 — 현재 이슈·리스크·기회 담론

> Bronze 테이블: `raw_discourse_data` (신규, 마이그레이션 `e2c5a7b9d3f4`) · 도메인: "지금 무엇이 화두인가"
> 최종 갱신: 2026-06-24

## 1. 목적

뉴스·커뮤니티·정부 보고서 등 **정성적 담론**을 수집해, 정량 신호(돈·특허)가 놓치는 *현재 이슈·리스크·기회*를 포착한다. ERD §4 `raw_discourse_data` source_type: `NEWS / REDDIT / BLIND / REPORT / JOB_INFO / SKILL_INFO / SUCCESS_CASE`.

## 2. 신규 테이블·인프라

이 도메인은 이번에 **0에서 신설**했다.
- 모델: `domain/master/models/bases/raw_discourse_data.py` (`headline`·`author_or_publisher`·`content_body`·`raw_metadata`·`published_at`, UNIQUE `source_url`).
- DTO `models/transfer/discourse_collect_dto.py` · Repository `hub/repositories/discourse_repository.py` · Ingest `hub/services/bronze_discourse_ingest_service.py`.
- 마이그레이션 `e2c5a7b9d3f4`(raw_discourse_data + verified_company_master). Neon 적용 완료.

## 3. 수집기 현황

| 소스 | 컬렉터 | source_type | 키 | 상태 |
|---|---|---|---|---|
| **뉴스 RSS**(한국경제·전자신문×2·ZDNet) | `discourse/news_rss/news_rss_collector.py` | `DISCOURSE_NEWS_RSS` | 불필요 | ✅ live검증 |
| 정부 보도자료(BOK·MOTIE) | `discourse/gov_report/gov_report_collector.py` | `DISCOURSE_GOV_REPORT` | 불필요 | 🟡 골격 |

> 네이버 검색/데이터랩은 논리상 담론이나 현재 `raw_economic_data`에 적재 중(차기 재배치 검토).

## 4. ⚠️ 실측 함정 (뉴스 RSS, 2026-06-24)

- **`feedparser.parse(URL)` 직접 호출 시 일부 매체(한국경제)가 "undefined entity" bozo로 0건.** → **브라우저 UA httpx(`economic/common/rss_wordpress_sync.fetch_html_sync`)로 받아 텍스트를 feedparser에 넘기면 정상**(한국경제 50건). UA 차단·인코딩 차이 때문. 컬렉터는 fetch-후-파싱 방식 사용.
- **시간대 함정(중요)**: feedparser `*_parsed`는 **UTC struct_time** → `time.mktime`(로컬 해석) 쓰면 KST 머신에서 9시간 오차. **`calendar.timegm` 사용**해야 `09:00 +0900 → 00:00Z` 정확. lead-lag(선행/후행 시차) 분석 정확도에 직결.
- 피드 URL은 죽기 쉬움(과거 techblog 사례) → 4피드 각각 try/except, 한 피드 실패해도 나머지 진행. 2026-06-24 4피드 전부 live 동작 확인.

## 5. 멱등성·운영
- `discourse_repository.insert_many_skip_duplicates`: source_url UNIQUE ON CONFLICT DO NOTHING + 배치(1000행) 헬퍼.
- 라우터 `POST /api/master/bronze/discourse/news-rss`(키 불필요). 스케줄러 일별.
- 실적재: 뉴스 RSS 가동 시 ~50/피드 신규 헤드라인 누적.

## 6. 차기 (문서만)
나무위키 최근변경(신조어 선행), YouTube KR Trending, 커뮤니티(theqoo/fmkorea — ToS 주의), 정부 보도자료 본구현. data_role 표준값(`DISCOURSE_SIGNAL`)으로 Silver 연결.

> 소스 카탈로그: [`backend/docs/sources/discourse_sources.md`](../../../../docs/sources/discourse_sources.md)
