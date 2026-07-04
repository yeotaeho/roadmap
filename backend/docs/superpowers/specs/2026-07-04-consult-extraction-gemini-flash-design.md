# SP-11 — 상담·자기모델 추출 LLM을 Gemini 2.5 Flash로 (provider-flexible, fail-loud) 설계

2026-07-04 확정. 상담 대화와 자기모델(RIASEC/Big Five) 추출이 쓰던 gpt-4o-mini를 Gemini 2.5 Flash로 교체한다.
경량 모델이라 지시 미준수·반복·드리프트가 심했다. OpenAI 호환 엔드포인트로 Gemini를 물리고, **폴백 없이
fail-loud**(키 없거나 콜 실패 시 에러 반환)로 문제를 표면화한다.

## 배경

`consult_service.py`·`self_model_extraction_service.py`가 `settings.llm_classify_model`(gpt-4o-mini)을 재사용.
gpt-4o-mini는 분류·추출용 경량 모델이라 상담 조향(다중 제약 지시)·성향 채점 품질이 낮았다(실사용에서 드리프트·
반복 확인). Gemini 2.5 Flash는 지시 준수·추론이 낫고(thinking) 저렴 — 이 용도에 가성비 최적. Google이 OpenAI
호환 엔드포인트(`https://generativelanguage.googleapis.com/v1beta/openai/`)를 제공해 기존 OpenAI SDK로 물릴 수 있다.

## 확정 결정 (사용자 확답)

| 결정 | 선택 |
|---|---|
| 모델 | **Gemini 2.5 Flash**(`gemini-2.5-flash`) — 상담 채팅·요약·플래너 + 자기모델 추출 |
| 폴백 | **없음(fail-loud)** — 키 없거나 Gemini 콜 실패 시 OpenAI로 안 내려가고 **에러 반환** |
| 범위 | 상담 대화 + 자기모델 추출(user_intelligence). 임베딩·세계-데이터 분류는 OpenAI 유지 |

## A. `LlmClient`에 `base_url` 추가

`backend/core/llm/client.py`.
```python
def __init__(self, api_key, model="gpt-4o-mini", embed_model="text-embedding-3-large", base_url: str | None = None):
    self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)  # None 이면 기존 OpenAI 동작
```
기존 호출부(base_url 미지정)는 무영향. Gemini는 OpenAI 호환 base_url 로 같은 SDK 사용.

## B. settings — provider config

`backend/core/config/settings.py`.
- `gemini_api_key: str | None`(env `GEMINI_API_KEY`, 기본 None)
- `user_llm_provider: str = "gemini"` (openai | gemini)
- `user_llm_model: str = "gemini-2.5-flash"`
- Gemini 호환 base_url 은 상수(core/llm 내). provider 를 openai 로 바꾸면 `user_llm_model` 도 openai 모델로 함께 바꾼다.

## C. 공용 해석 헬퍼 — fail-loud (폴백 없음)

`backend/core/llm/provider.py`(신설). `resolve_user_llm(settings) -> tuple[api_key, model, base_url]`.
```
provider == "gemini":  gemini_api_key 없으면 → ValueError("GEMINI_API_KEY 미설정") raise
                       있으면 → (gemini_api_key, user_llm_model, GEMINI_BASE_URL)
provider == "openai":  openai_api_key 없으면 → ValueError raise
                       있으면 → (openai_api_key, user_llm_model, None)
그 외 provider       :  ValueError raise
```
- **크로스-프로바이더 폴백 없음** — gemini 선택 시 gemini 키 없으면 에러(OpenAI 대체 안 함).

## D. 서비스 배선 + 에러 표면화

두 서비스가 `resolve_user_llm`을 쓴다.

- **ConsultService** — `__init__`에서 `resolve_user_llm`을 try 로 호출. 성공 시 `(api_key, model, base_url)` 저장,
  실패 시 `self._llm_error = str(e)` 저장(설정 자체는 안 깨져 세션 조회 등 비-LLM 엔드포인트는 계속 동작).
  streamer·summarizer·planner 가 저장된 base_url 로 `LlmClient` 생성.
  `stream_sse` — 기존 `if not self._api_key` 자리를 `if self._llm_error` 로: 해석 실패면 `_sse({"type":"error",
  "message":"상담 모델 설정 오류 — GEMINI_API_KEY 확인"})` + done 방출(프론트가 에러 표시). Gemini 콜이 스트림
  중 실패하면 기존 respond 에러 경로(`{"type":"error"}`)로 그대로 노출(폴백 안 함).
- **SelfModelExtractionService** — `__init__`에서 `resolve_user_llm` 호출(실패 시 raise 허용 — 모든 메서드가 LLM
  의존이라). `_default_extractor` 가 base_url 로 `LlmClient` 생성. 추출 실패(키 없음·콜 오류)는 **명확한 에러 로그로
  실패**하고 자기모델 미갱신(즉시 추출 경로·일일 배치의 기존 try/except 가 잡아 로깅). **OpenAI 대체 없음** — 성향
  지도가 안 채워지는 것으로 문제가 드러남.

## E. 검증

- **순수 `resolve_user_llm`** — (a)gemini+키 → gemini 튜플(base_url 포함) (b)gemini+키없음 → ValueError
  (c)openai → openai 튜플(base_url None) (d)미지 provider → ValueError.
- **`LlmClient` base_url 전달** — `AsyncOpenAI` 에 base_url 이 전달되는지(client.base_url 확인).
- **ConsultService 에러 표면화** — `_llm_error` 세팅 시 `stream_sse` 가 error SSE 방출(monkeypatch resolve).
- **회귀** — FakeLLM 상담·추출 스위트(streamer/extractor 주입이라 실 LLM 우회) 불변.
- **라이브 verify(키 필요)** — `GEMINI_API_KEY` 넣고 Docker 재기동 후: 상담이 축을 주도적으로 파고들고 반복·드리프트
  감소, `response_format=json_object`(플래너·추출)가 Gemini 호환 엔드포인트에서 동작하는지 확인. 미동작 시 각 파서
  안전 폴백은 있으나 품질 저하 — 키 넣고 실측.

## 범위 밖

- 임베딩(text-embedding-3-large 유지 — Gemini 무관). 세계-데이터 분류(섹터·gap·chance = gpt-4o-mini 유지, 성향 무관).
- 모델 A/B 자동 라우팅·비용 가드. 프롬프트 자체 개편(SP-10에서 완료).

## 분해

- **Task 1** — `LlmClient` base_url + `resolve_user_llm`(provider.py) + settings + 순수/전달 테스트.
- **Task 2** — ConsultService·SelfModelExtractionService 배선 + 에러 표면화 + 회귀.

## 파일 지도

| 영역 | 파일 |
|---|---|
| 클라이언트 | `backend/core/llm/client.py`(base_url) |
| 해석 헬퍼 | `backend/core/llm/provider.py`(신설, `resolve_user_llm`·`GEMINI_BASE_URL`) |
| 설정 | `backend/core/config/settings.py`(gemini_api_key·user_llm_provider·user_llm_model) |
| 배선 | `backend/domain/user_intelligence/hub/services/consult_service.py`·`self_model_extraction_service.py` |
| 테스트 | `backend/scripts/user_llm_resolve_test.py`(신규) · consult/extraction 회귀 |
