# master 도메인 작업 기록 (Audit Trail)

최신 항목을 맨 위에 추가(역순). 형식은 `CLAUDE.md` 작업 기록 규칙 참고.

---

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
