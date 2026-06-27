# master 도메인 작업 기록 (Audit Trail)

최신 항목을 맨 위에 추가(역순). 형식은 `CLAUDE.md` 작업 기록 규칙 참고.

---

## 2026-06-27 — K-Startup 공고 본문 보강 (상세 페이지 fetch)

- **무엇** — `raw_opportunity_data` OPP_KSTARTUP_GRANT 278건 중 88%(245건)이 `raw_content` 200자 미만(API `pbanc_ctnt` 130자 요약만 제공). 상세 페이지 HTML을 fetch해 `.information_list` 컨테이너에서 본문을 추출·교체하는 보강 로직 추가.
- **왜** — Silver `refined_chance_insights`가 `raw_content`를 LLM 입력으로 쓰는데, 130자 요약만으로는 지원 자격·신청방법 등 핵심 정보가 누락돼 청년 기회 매칭 품질이 떨어짐.
- **어디** — [`kstartup_collector.py`](../hub/services/collectors/opportunity/kstartup/kstartup_collector.py): `extract_kstartup_body()`(신규), `_ENRICH_THRESHOLD=200`, `_KSTARTUP_BODY_SELECTORS`(.information_list 우선 + 3개 폴백), `collect()` 끝단 `asyncio.Semaphore(5)` 보강 루프. [`scripts/bronze_expansion_parse_test.py`](../../../scripts/bronze_expansion_parse_test.py): `test_kstartup_body_enrichment()` 6건 추가.
- **검증** — `bronze_expansion_parse_test.py` 58/58 PASS(신규 6건 포함). 커밋 `d4daee7`.
- **후속** — `.information_list` 셀렉터는 샘플 1건 기준. 실 수집 로그 `본문 보강 완료: N/M건` 비율 모니터링 권장. push 미완료(Task F, 핸드오프 문서 참고).

## 2026-06-27 — 뉴스 RSS 본문 보강으로 content_body 결측 해소 (④ fetch 손실)
- **무엇** — 한국경제 등 RSS summary 가 없거나 짧은 매체에서 원문 페이지를 fetch 해 본문을 추출·보강. `extract_article_body`(schema.org `itemprop=articleBody` 우선 + 매체 공통 셀렉터 폴백) + `parse_feed_entries(fetch_article DI)`. 280자 미만 항목만 보강하고, fetch 실패·결과가 더 짧으면 기존 summary 유지.
- **왜** — Bronze 결측 측정 결과 discourse `content_body` 35.7% 결측(한국경제 100%). RSS 가 본문을 주지 않는데 수집기가 원문 보강을 안 해 "원문엔 있는데 못 가져오는" 손실 발생. 같은 코드베이스 Platum 의 `fetch_article_if_short` 패턴이 news_rss 엔 부재했다.
- **어디** — [news_rss_collector.py](./../hub/services/collectors/discourse/news_rss/news_rss_collector.py) `extract_article_body`·`parse_feed_entries`·`_fetch_article_body`·`collect_sync`.
- **검증** — `scripts/bronze_expansion_parse_test.py` 46 PASS(본문 보강 7건 추가, 기존 39건 회귀 없음). 라이브 end-to-end: 한국경제 `content_body` 0→1661/1325/1695자. 측정 스크립트 `scripts/bronze_null_audit.py`. 커밋 `d6948d4`(측정)·`e433fb1`(보강).
- **후속** — 전자신문 티저(227자)도 보강 대상이나 전체 collect_sync 라이브는 미검증. fetch 실패·보강 건수 stats 가시화 미적용. 다음: KIAT `published_at` 96.4% NULL(Pulse 시계열 근간) 착수 예정.

## 2026-06-26 — 사람인 채용 수집 직무·스킬 키워드 보강 (⑤b)
- **무엇** — 사람인 수집기 키워드를 섹터급 10개 + 직무·스킬급 14개(데이터엔지니어·백엔드·데브옵스·PM·UXUI 등)로 확장. 기본 수집을 섹터+직무 결합 세트(`_DEFAULT_KEYWORDS`)로.
- **왜** — 평가 ⑤ "직무 해상도 부재"(산업 신호는 두꺼우나 '어떤 직무·스킬이 뜨는가'에 답할 Bronze 약함) 보강. 점핏은 사람인 계열로 별도 불필요, 원티드 OpenAPI는 키 신청 후 추가 가능.
- **어디** — [saramin_recruit_collector.py](./../hub/services/collectors/people/saramin/saramin_recruit_collector.py) `_JOB_KEYWORDS`·`_DEFAULT_KEYWORDS`.
- **검증** — `scripts/bronze_expansion_parse_test.py` 39 PASS(키워드 세트 검증 추가). 커밋 `4d2d64b`.
- **후속** — 일 500콜 한도 내 ~24키워드. 직무 신호의 Silver/serving 소비처(직무 수요 랭킹 등)는 미연결.

## 2026-06-26 — MSIT·MFDS 수집 연도 미명시 시 현재 연도 해석 (①)
- **무엇** — Bronze 수집 연도 시한폭탄 수정. `_resolve_board`·`ingest_mfds_press`가 target_year 미명시 시 하드코딩 2026 보드를 쓰던 것을 `datetime.now().year` 해석으로 변경.
- **왜** — 스케줄러가 연도를 주입하지 않아, 해가 바뀌면 MSIT(보도·사업공고)·MFDS가 연도 필터로 전건 탈락 → 예외 없이 0건 수집(무음 사망). Bronze·Silver 데이터 퀄리티 평가에서 식별.
- **어디** — [bronze_economic_ingest_service.py](./../hub/services/bronze_economic_ingest_service.py) `_resolve_board`·`ingest_mfds_press`. 원천 함정: [msit_bbs_collector.py](./../hub/services/collectors/economic/msit/msit_bbs_collector.py) `target_year=2026`, [mfds_bbs_collector.py](./../hub/services/collectors/economic/mfds/mfds_bbs_collector.py) `target_year=2026`.
- **검증** — `scripts/bronze_year_resolution_test.py` 5 PASS. 커밋 `d434277`.
- **후속** — 연말 경계(직전 연도 잔여 게시물) 보강은 미적용. 평가에서 함께 지적된 투자 금액 None(IPO·NPS·RSS·ALIO)·직무 수요 소스 부재는 별도 설계 필요.
