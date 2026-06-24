# Discourse 소스 카탈로그 — raw_discourse_data (이슈·리스크·기회)

> 담론·정성 흐름. 뉴스·커뮤니티·보고서로 현재 이슈/리스크/기회를 포착.
> 상태: ✅ 구현 / 🟡 골격 / 📄 문서(차기 후보).
> 조사·검증일 2026-06-23. (신규 테이블 — 마이그레이션 `e2c5a7b9d3f4`)

## 구현·후보 소스

| 소스 | 엔드포인트 | 데이터 | source_type | 키 | 상태 |
|---|---|---|---|---|---|
| 한국경제 경제 RSS | `https://www.hankyung.com/feed/economy` | 경제 헤드라인·본문 | `DISCOURSE_NEWS_RSS` | 불필요 | ✅ live검증 |
| 전자신문 오늘의뉴스 | `https://rss.etnews.com/Section901.xml` | IT·기술 뉴스 | `DISCOURSE_NEWS_RSS` | 불필요 | ✅ live검증 |
| 전자신문 속보 | `https://rss.etnews.com/Section902.xml` | 속보 | `DISCOURSE_NEWS_RSS` | 불필요 | ✅ live검증 |
| ZDNet Korea | `https://feeds.feedburner.com/zdkorea` | IT 산업 뉴스 | `DISCOURSE_NEWS_RSS` | 불필요 | ✅ live검증 |
| 정부 보도자료(한국은행·산업부) | bok.or.kr / motie.go.kr 게시판(BS4) | 정책 담론(REPORT) | `DISCOURSE_GOV_REPORT` | 불필요 | 🟡 골격 |
| 나무위키 최근변경 | namu.wiki/recent | 신조어·급부상 트렌드 | — | 불필요(ToS 주의) | 📄 |
| YouTube KR Trending | youtube/v3 | K-콘텐츠 인기 | — | YOUTUBE_DATA(신규) | 📄 |
| 커뮤니티(theqoo·fmkorea) | 크롤링 | 20–30대 반응 | — | 불필요(ToS 주의) | 📄 |

## 구현 메모 / 함정

- **뉴스 RSS (2026-06-23 live 확인 — 4피드 전부 동작, 멱등성 OK)**: `platum_collector` 구조 미러하되 **투자 필터 제거**, 전 헤드라인 수집. 매체별 `(publisher, category, url)` 튜플. 피드 죽으면 해당 피드만 스킵.
- **함정(중요)**: `feedparser.parse(URL)`로 직접 호출하면 한국경제 피드가 "undefined entity" bozo로 **0건**. **브라우저 UA httpx(`fetch_html_sync`)로 받아 텍스트를 feedparser에 넘기면 정상**(한국경제 50건). UA 차단·인코딩 차이 때문 → 컬렉터는 fetch 후 파싱 방식 사용.
- **시간대 함정(중요)**: feedparser `*_parsed` 는 **UTC struct_time** → `time.mktime`(로컬 해석) 쓰면 KST 머신에서 9h 오차. **`calendar.timegm` 사용**해야 `09:00 +0900 → 00:00Z` 정확. lead-lag 분석 정확도에 직결.
- **네이버 검색/데이터랩**: 논리상 담론이나 현재 `raw_economic_data`에 적재 중(이번엔 이전하지 않음). 차기 통합 시 `DISCOURSE_*` 로 재배치 검토.
- **수집기**: `collectors/discourse/news_rss/news_rss_collector.py` (✅), `collectors/discourse/gov_report/gov_report_collector.py` (🟡 골격).
