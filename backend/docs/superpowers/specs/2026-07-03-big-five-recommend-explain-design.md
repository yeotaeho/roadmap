# SP-6① — Big Five를 추천 설명 레이어에 활용 설계

2026-07-03 확정. SP-5에서 채점한 Big Five 성격 5요인을 추천 **설명 레이어**에 녹인다. 점수·임베딩·순위는
그대로 두고, "왜 이 추천"을 쓰는 LLM이 성격-적합 서술을 (해당될 때만) 더한다.

## 확정 결정 (사용자 확답)

| 결정 | 선택 |
|---|---|
| 녹일 위치 | **설명 레이어만** — 임베딩·Sync/Chance 점수·순위 불변 |

**왜 설명 레이어인가** — RIASEC(흥미)은 "어떤 분야"라 섹터·공고 내용에 자연 매칭되지만, Big Five(성격)는
"어떻게 일하나·어떤 환경"이라 섹터 임베딩·공고 텍스트에 그대로 넣으면 흥미 기반 매칭을 흐리는 노이즈가 될
수 있다. 성격의 제자리는 "이 일이 당신과 왜 맞는지"를 설명하는 레이어다.

## 배경

- 현재 임베딩(`self_model_terms`)·추천 설명(`_build_user_context`)은 `riasec.top_codes`·서사·긍정 근거만 쓰고
  Big Five는 미사용. SP-5로 `user_self_model.big_five = {scores:{O,C,E,A,N}, raw, weights}`가 채워진다.
- 추천 설명은 일일 배치 `RecommendExplainService`가 사용자당 LLM 1회로 Sync 상위·Chance 상위 항목의
  "왜 이 추천"을 생성한다(SP-3). 그 LLM 컨텍스트에 Big Five 특질을 추가한다.

## A. 데이터 흐름 (점수·임베딩 불변)

```
fetch_user_context: SELECT 에 sm.big_five 추가 → dict 에 big_five
        ▼
_build_user_context(순수): big_five → personality_traits 리스트 파생
        ▼
explain_recommendations 컨텍스트에 personality_traits 주입
        ▼
"왜 이 추천" 문장에 성격-적합 서술(공고가 해당 방식을 분명히 포함할 때만)
```

## B. 특질 파생 (순수 함수)

신규 순수 함수 `big_five_traits(big_five: dict | None) -> list[str]`(recommend_explain_service.py).

- **뚜렷한 특질만** — 상수 `TRAIT_MARGIN = 12`. 각 축 display 점수가 50에서 `TRAIT_MARGIN` 이상 벗어난 것만
  서술어로. 파악 중(중립, |score−50| < 12)인 축은 건너뜀(억지 서술 방지). big_five null·scores 없으면 빈 리스트.
- **강점·중립 서술어 매핑**(방향별):

| 축 | 높음(≥62) | 낮음(≤38) |
|---|---|---|
| O 개방성 | 새로움·아이디어에 개방적 | 익숙함·실용을 선호 |
| C 성실성 | 체계적이고 성실함 | 유연하고 즉흥적 |
| E 외향성 | 사람과 교류에서 에너지를 얻음 | 혼자 깊이 집중하는 걸 선호 |
| A 우호성 | 협력적이고 배려심 있음 | 독립적이고 솔직함 |
| N 신경성 → **정서안정성(100−N)** | (안정성 높음, N낮음) 차분하고 정서적으로 안정적 | (안정성 낮음, N높음) 신중하게 위험을 살핌 |

- **신경성은 정서안정성 관점만** — 병리·약점으로 규정하지 않는다(SP-5 정책 재사용). N 높음도 "신중하게
  위험을 살핌" 같은 중립·강점 서술로. 절대 "불안정·예민함" 식 단정 금지.

## C. 프롬프트

`_RECOMMEND_EXPLAIN_SYSTEM_PROMPT`에 personality_traits 활용 지침 추가.

- 사용자 컨텍스트에 `personality_traits`(성격 특질 서술어)를 받는다.
- 성격-적합은 **공고·항목이 그 일하는 방식을 분명히 포함할 때만** 언급하라(예 "협업 중심" 공고 ↔ 협력적 성향).
  근거가 불분명하면 성격을 억지로 끌어들이지 마라(환각 금지).
- 성격은 강점·중립 관점으로만 서술하고, 약점·병리로 규정하지 마라.
- 성격 적합은 넓은 섹터(Sync)보다 개별 공고(Chance)에 더 자연스럽게 적용된다.

## D. 코드 지점

- `recommend_explain_repository.py` — `_FETCH_USER_CONTEXT` SELECT 에 `sm.big_five` 추가, `fetch_user_context`
  반환 dict 에 `"big_five": r.big_five`.
- `recommend_explain_service.py` — `big_five_traits` 순수 함수 + `_build_user_context` 반환에 `personality_traits`.
- `core/llm/client.py` — `_RECOMMEND_EXPLAIN_SYSTEM_PROMPT` 지침 추가.

## E. 테스트

- 순수 `big_five_traits` — (a) 뚜렷한 축만 서술(임계 12), (b) 중립 축 스킵, (c) N→정서안정성 프레이밍(높은 N도
  중립·강점 서술·병리 금지), (d) big_five null/scores 없음 → 빈 리스트, (e) 낮은 쪽 서술어.
- `_build_user_context` — big_five 있으면 personality_traits 채움, 없으면 빈 리스트. 민감 근거 미주입 불변.
- 서비스 통합 — FakeLLM 컨텍스트에 personality_traits 전달 확인. `recommend_explain_service_test` 회귀
  (fetch_user_context 가 big_five 포함해도 기존 동작 유지).

## F. 범위 밖 (후속)

- 임베딩·Sync/Chance 점수에 Big Five 반영 — 의도적 제외(성격은 설명 레이어). 필요성 확인 시 별도 SP.
- ② user_form 자기모델 입력 UI + 축별 provenance. ③ 규준집단 백분위.

## 파일 지도

| 영역 | 파일 |
|---|---|
| 리포(컨텍스트) | `backend/domain/market_insight/hub/repositories/recommend_explain_repository.py` |
| 서비스(특질 파생) | `backend/domain/market_insight/hub/services/recommend_explain_service.py` |
| 프롬프트 | `backend/core/llm/client.py` |
