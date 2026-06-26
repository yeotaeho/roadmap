# master 도메인 작업 기록 (Audit Trail)

최신 항목을 맨 위에 추가(역순). 형식은 `CLAUDE.md` 작업 기록 규칙 참고.

---

## 2026-06-26 — MSIT·MFDS 수집 연도 미명시 시 현재 연도 해석 (①)
- **무엇** — Bronze 수집 연도 시한폭탄 수정. `_resolve_board`·`ingest_mfds_press`가 target_year 미명시 시 하드코딩 2026 보드를 쓰던 것을 `datetime.now().year` 해석으로 변경.
- **왜** — 스케줄러가 연도를 주입하지 않아, 해가 바뀌면 MSIT(보도·사업공고)·MFDS가 연도 필터로 전건 탈락 → 예외 없이 0건 수집(무음 사망). Bronze·Silver 데이터 퀄리티 평가에서 식별.
- **어디** — [bronze_economic_ingest_service.py](./../hub/services/bronze_economic_ingest_service.py) `_resolve_board`·`ingest_mfds_press`. 원천 함정: [msit_bbs_collector.py](./../hub/services/collectors/economic/msit/msit_bbs_collector.py) `target_year=2026`, [mfds_bbs_collector.py](./../hub/services/collectors/economic/mfds/mfds_bbs_collector.py) `target_year=2026`.
- **검증** — `scripts/bronze_year_resolution_test.py` 5 PASS. 커밋 `d434277`.
- **후속** — 연말 경계(직전 연도 잔여 게시물) 보강은 미적용. 평가에서 함께 지적된 투자 금액 None(IPO·NPS·RSS·ALIO)·직무 수요 소스 부재는 별도 설계 필요.
