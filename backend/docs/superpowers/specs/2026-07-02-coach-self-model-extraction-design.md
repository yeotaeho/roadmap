# 대화 → 자기모델 증분 추출 (SP-2b) 설계

> **목적** — 코치 대화에서 사용자의 성향·가치관·호불호·제약을 **비동기로 추출**해 SP-1 자기모델에 축적한다. "AI 상담실=개인화 본가"의 마지막 고리 — 대화가 곧 자기이해가 된다.
> **작성일** — 2026-07-02. 소비: [자기모델 데이터층](2026-07-01-ai-coach-self-model-design.md)(SP-1) · [코치 영속화](2026-07-01-coach-session-persistence-design.md)(SP-2a). 다음: SP-3(추천 반영).

---

## 1. 배경 — 왜

SP-1이 자기모델 저장소를, SP-2a가 영속 대화를 만들었다. 남은 것은 **대화를 자기모델로 바꾸는 추출기**다. 사용자가 폼을 채우지 않아도, 코치와 이야기하는 것만으로 성향·호불호·가치관이 쌓여 Sync·Chance 추천이 두꺼워진다.

## 2. 확정 결정(브레인스토밍)
- **active 세션 증분 추출** — 재개 모델상 세션이 거의 안 끝나므로, 스케줄러가 주기적으로 **마지막 추출 이후 새 메시지**를 가진 세션에서 증분 추출(living 자기모델). `summarized_until` 패턴 재사용.
- **근거+서사+저위험 구조축** — evidence(호불호·가치·제약·민감·포부)를 핵심으로, narrative_summary + RIASEC top_codes(확신 시)를 추가. numeric big_five/RIASEC-6점수 정밀추정은 보류(chat 노이즈). confidence 정직 부여 → SP-1 게이팅(0.40)이 거름.

## 3. 데이터 모델
- `coach_sessions.extracted_until` **INTEGER NOT NULL DEFAULT 0** 추가(이미 추출한 메시지 수). `extracted_at`(SP-2a 기존)은 마지막 추출 시각으로 사용. 마이그레이션 1건(추가만).

## 4. 추출 LLM (`core/llm/client.py`)
- 상수 `_SELF_MODEL_EXTRACT_SYSTEM_PROMPT` + 메서드 `extract_self_model(messages: list[dict]) -> dict` + 순수 파서 `_parse_self_model_extract`.
- 출력 JSON(파서가 검증):
```json
{
  "riasec_top_codes": ["I","A","S"],        // 확신 시, 아니면 []
  "riasec_confidence": 0.0,                  // 0~1
  "narrative": "...",                        // 한 줄 자기서사, 없으면 null
  "evidence": [
    {"dimension":"like|dislike|value|constraint|sensitive|aspiration|skill_signal|other",
     "polarity":"like|dislike|neutral|null", "content":"근거 문장",
     "confidence":0.0, "is_sensitive": false}
  ]
}
```
- 파서 규칙: riasec_top_codes 는 R/I/A/S/E/C 부분집합만(그 외 제거), confidence 0~1 클램프, evidence dimension 닫힌 집합 외는 'other', content 없으면 항목 드롭, is_sensitive bool 강제. 빈/파싱불가 → 빈 결과(무추출).
- **프라이버시 프롬프트 규칙** — 민감(트라우마·개인적 제약)은 **사용자가 스스로 드러낸 것만** is_sensitive=true 로. 능동적으로 캐묻거나 추론하지 않는다.

## 5. 추출 서비스 (`ai_coach/hub/services/self_model_extraction_service.py`)
`SelfModelExtractionService(db)` — 코치 대화(ai_coach) 읽고 자기모델(user_intelligence) 씀. LLM 주입 가능(테스트 fake).
- `async extract_session(user_id, session_id) -> dict`:
  1. `get_session` → `extracted_until`, `count = count_messages`. `cutoff = count`.
  2. `new_msgs = fetch_messages()[extracted_until:cutoff]`. `if len(new_msgs) < MIN_NEW(기본 6): return {"skipped": True}`.
  3. `result = await self._extractor(new_msgs)`(기본 `LlmClient.extract_self_model`).
  4. 구조축 매핑 → `incoming = {"riasec": {"top_codes": result["riasec_top_codes"]} if result["riasec_top_codes"] else None, "big_five": None, "narrative_summary": result["narrative"], "axis_confidence": {"riasec": result["riasec_confidence"]}}` → `SelfModelService(db).upsert_structured(user_id, incoming, source="coach_extraction")`(SP-1 병합·게이팅).
  5. 근거 → `SelfModelService(db).append_evidence(user_id, result["evidence"], source="coach_extraction")`(dedup·민감 격리는 SP-1 리포지토리).
  6. `update_extracted(session_id, cutoff)`(extracted_until=cutoff, extracted_at=now).
  7. 반환 `{"extracted": len(new_msgs), "evidence": <n>, "riasec": bool}`.
- `async extract_pending(limit=20) -> dict`: `fetch_extractable_sessions(MIN_NEW, limit)`(count>extracted_until+MIN_NEW) → 각 `extract_session`. 실패는 건별 격리(한 세션 실패가 배치 중단 아님). 반환 처리 수.

## 6. 리포지토리 확장 (`coach_session_repository.py`)
- `get_session` 반환에 `extracted_until` 추가(_GET 에 컬럼).
- `async update_extracted(session_id, extracted_until) -> None` — `extracted_until` + `extracted_at=now()`.
- `async fetch_extractable_sessions(min_new, limit) -> list[dict]` — `SELECT s.id, s.user_id FROM coach_sessions s WHERE (SELECT count(*) FROM coach_messages m WHERE m.session_id=s.id) > s.extracted_until + :min_new ORDER BY ... LIMIT :limit`(active·ended 모두).

## 7. 스케줄러 (`core/scheduler.py`)
- `_job_self_model_extract` → `SelfModelExtractionService(session).extract_pending(limit)`. **일일**(09:00 파이프라인 또는 전용 CronTrigger). LLM 비용 고려해 매시간 아님. 멱등(extracted_until), 독립 세션. 실패 격리·로깅.

## 8. 성공 기준
1. 마이그레이션으로 `extracted_until` 존재.
2. 세션에 대화가 쌓이면 추출이 자기모델을 갱신 — 근거 append + (확신 시) RIASEC top_codes·서사 upsert.
3. 멱등 — 같은 세션 재추출은 새 메시지 없으면 무변화(evidence 중복 없음, extracted_until 불변).
4. MIN_NEW 미만 신규는 스킵.
5. 민감 근거는 격리 저장(SP-1) — 기본 조회·추천 제외.
6. 저confidence 구조축은 SP-1 게이팅으로 미기록(값), 신뢰도만 반영.

## 9. 테스트 전략
- `scripts/self_model_extract_parse_test.py` — 순수 파서(riasec 필터·confidence 클램프·dimension 닫힌집합·빈결과·is_sensitive).
- `scripts/self_model_extraction_test.py`(Neon, fake extractor) — 코치 세션+메시지 seed → `extract_session` → 자기모델 upsert(riasec/narrative)·evidence append·`extracted_until` 전진 검증 → 재추출 멱등(무변화) → MIN_NEW 스킵 → `extract_pending` 선택. 시작·종료 클린업.

## 10. 범위 밖 / 후속
- **능동 탐침**(코치가 빈 축을 물어봄) — 코치 프롬프트 변경, 별도.
- **numeric big_five/RIASEC-6점수 정밀추정** — 신호 축적·정식 진단 후.
- **임베딩 반영**(추출된 축·근거를 사용자 임베딩에) — **SP-3**.
- 자기모델을 사용자에게 보여주는 UI — SP-4.
- 추출 감사 로그·사용자 삭제권("이 이야기 잊어줘") — 프라이버시 정책 후속.

## 11. 가정·미해결
- **cutoff 안정성** — `extracted_until`은 메시지 count(삭제 없는 append-only라 인덱스 안정, `summarized_until`과 동일 전제).
- **요약 vs 추출 독립** — `summarized_until`(컨텍스트 압축)과 `extracted_until`(자기모델 추출)은 별개 지점. 서로 간섭 없음.
- **추출 주기** — 일일 기본. 비용·신선도 보고 `SELF_MODEL_EXTRACT_*` env 로 조정(후속).
- **MIN_NEW=6** — 너무 잦은 저품질 추출 방지. 실사용 후 튜닝.
