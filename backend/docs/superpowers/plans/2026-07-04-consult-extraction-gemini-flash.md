# SP-11 상담·추출 LLM을 Gemini 2.5 Flash로 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상담(채팅·요약·플래너)과 자기모델 추출이 쓰던 gpt-4o-mini를 Gemini 2.5 Flash로 provider-flexible하게 교체하고, 키 없음·콜 실패 시 OpenAI 폴백 없이 fail-loud로 에러를 낸다.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-04-consult-extraction-gemini-flash-design.md`. `LlmClient`에 `base_url`(OpenAI 호환 엔드포인트로 Gemini) + `core/llm/provider.py`의 `resolve_user_llm`(fail-loud) + settings provider config. ConsultService·SelfModelExtractionService 배선.

**Tech Stack:** OpenAI SDK(AsyncOpenAI, base_url로 Gemini 호환 엔드포인트) · Gemini 2.5 Flash · pydantic settings.

## Global Constraints

- 한국어 문장 종결 `.` `?` `!` 만. 새 소스 파일 첫 줄 한 줄 한국어 역할 주석. 커밋 논리 단위·`git add .` 금지·트레일러 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **폴백 없음(fail-loud)** — provider=gemini 인데 키 없으면 `ValueError`. 콜 실패는 에러로 노출(OpenAI 대체 금지).
- **기본 provider=gemini** — 단, `user_llm_model` 기본은 빈 문자열이고 resolve 가 provider별 기본(gemini→gemini-2.5-flash, openai→gpt-4o-mini)을 채운다. 그래서 `USER_LLM_PROVIDER=openai` 하나만으로 OpenAI 로 전환된다(모델명 별도 지정 불필요).
- 임베딩·세계-데이터 분류(섹터·gap·chance)는 OpenAI gpt-4o-mini 유지 — 무변경.
- 백엔드 테스트 `backend/scripts/*_test.py`(cwd `backend/`).

---

### Task 1: LlmClient base_url + resolve_user_llm + settings

**Files:**
- Modify: `backend/core/llm/client.py` (`LlmClient.__init__` base_url)
- Create: `backend/core/llm/provider.py` (`resolve_user_llm`·`GEMINI_BASE_URL`)
- Modify: `backend/core/config/settings.py` (gemini_api_key·user_llm_provider·user_llm_model)
- Test(신규): `backend/scripts/user_llm_resolve_test.py`

**Interfaces:**
- Produces: `LlmClient(api_key, model=..., embed_model=..., base_url=None)` · `resolve_user_llm(settings) -> tuple[str, str, str|None]`(api_key, model, base_url; fail-loud) · `GEMINI_BASE_URL`.

- [ ] **Step 1: resolve 순수 실패 테스트**

`backend/scripts/user_llm_resolve_test.py` 생성.

```python
# LLM 프로바이더 해석 순수 테스트 — gemini/openai·키 유무·미지 provider·base_url.

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.provider import GEMINI_BASE_URL, resolve_user_llm

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


class S:
    def __init__(self, provider="gemini", model="", gk="gk", ok="ok"):
        self.user_llm_provider = provider
        self.user_llm_model = model
        self.gemini_api_key = gk
        self.openai_api_key = ok


def run() -> int:
    check("gemini+키 → gemini 튜플", resolve_user_llm(S()) == ("gk", "gemini-2.5-flash", GEMINI_BASE_URL))
    check("gemini 모델 오버라이드", resolve_user_llm(S(model="gemini-1.5-pro")) == ("gk", "gemini-1.5-pro", GEMINI_BASE_URL))
    try:
        resolve_user_llm(S(gk=None))
        check("gemini 키없음 raise", False, "no raise")
    except ValueError:
        check("gemini 키없음 raise", True)
    check("openai → openai 튜플(base_url None)", resolve_user_llm(S(provider="openai")) == ("ok", "gpt-4o-mini", None))
    check("openai 모델 오버라이드", resolve_user_llm(S(provider="openai", model="gpt-4o")) == ("ok", "gpt-4o", None))
    try:
        resolve_user_llm(S(provider="openai", ok=None))
        check("openai 키없음 raise", False, "no raise")
    except ValueError:
        check("openai 키없음 raise", True)
    try:
        resolve_user_llm(S(provider="claude"))
        check("미지 provider raise", False, "no raise")
    except ValueError:
        check("미지 provider raise", True)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/user_llm_resolve_test.py` (cwd `backend/`)
Expected: `ModuleNotFoundError`(provider 미존재).

- [ ] **Step 3: provider.py 구현**

`backend/core/llm/provider.py` 생성.

```python
# LLM 프로바이더 해석 — 상담·자기모델 추출용(openai | gemini). 폴백 없이 fail-loud.

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

_DEFAULT_MODEL = {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini"}


def resolve_user_llm(settings) -> tuple[str, str, str | None]:
    """상담·추출 LLM 설정 해석 → (api_key, model, base_url). 키 없음·미지 provider 는 ValueError(폴백 없음)."""
    provider = (getattr(settings, "user_llm_provider", None) or "gemini").lower()
    if provider not in _DEFAULT_MODEL:
        raise ValueError(f"알 수 없는 user_llm_provider: {provider}")
    model = getattr(settings, "user_llm_model", "") or _DEFAULT_MODEL[provider]
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY 미설정 — Gemini provider 사용 불가")
        return settings.gemini_api_key, model, GEMINI_BASE_URL
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY 미설정 — OpenAI provider 사용 불가")
    return settings.openai_api_key, model, None
```

- [ ] **Step 4: LlmClient base_url**

`backend/core/llm/client.py` `LlmClient.__init__` 을 교체.

```python
    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 embed_model: str = "text-embedding-3-large", base_url: str | None = None):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._embed_model = embed_model
```
(기존 시그니처에 `base_url=None` 추가만 — 기존 호출부 무영향.)

- [ ] **Step 5: settings 추가**

`backend/core/config/settings.py` 의 `llm_classify_model` 근처에 추가.

```python
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    user_llm_provider: str = Field(default="gemini", validation_alias="USER_LLM_PROVIDER")
    user_llm_model: str = Field(default="", validation_alias="USER_LLM_MODEL")
```

- [ ] **Step 6: base_url 전달 단정 + resolve 통과**

`user_llm_resolve_test.py` 에 LlmClient base_url 단정 추가.

```python
    from core.llm.client import LlmClient
    c1 = LlmClient(api_key="x", model="m", base_url="https://ex.test/v1/")
    check("base_url 전달", str(c1._client.base_url).startswith("https://ex.test"), str(c1._client.base_url))
    c2 = LlmClient(api_key="x", model="m")
    check("base_url None 기본 OpenAI", "openai.com" in str(c2._client.base_url), str(c2._client.base_url))
```

Run: `python scripts/user_llm_resolve_test.py`
Expected: `결과: PASS=9 FAIL=0`(resolve 7 + base_url 2).

- [ ] **Step 7: 커밋**

```bash
git add backend/core/llm/client.py backend/core/llm/provider.py backend/core/config/settings.py backend/scripts/user_llm_resolve_test.py
git commit -m "feat(sp11): LlmClient base_url + resolve_user_llm(fail-loud) + Gemini provider settings"
```

---

### Task 2: ConsultService·추출 배선 + 에러 표면화 + 회귀

**Files:**
- Modify: `backend/domain/user_intelligence/hub/services/consult_service.py` (resolve·base_url·`_llm_error`·stream_sse)
- Modify: `backend/domain/user_intelligence/hub/services/self_model_extraction_service.py` (resolve·base_url·`_llm_error`)
- Modify(테스트): `consult_service_test.py`·`consult_stream_test.py`·`consult_endpoint_test.py`·`self_model_extraction_test.py` (USER_LLM_PROVIDER=openai) · 신규 에러표면 케이스

**Interfaces:**
- Consumes: Task 1 `resolve_user_llm`·`LlmClient(base_url=...)`.
- Produces: 두 서비스가 provider config 로 LLM 생성. ConsultService `_llm_error`(해석 실패 메시지) → stream_sse error SSE. SelfModelExtractionService `_llm_error` → `_default_extractor` raise.

- [ ] **Step 1: ConsultService 배선**

`consult_service.py` 상단 import 에 `from core.llm.provider import resolve_user_llm` 추가. `__init__`(현재 112-114행) 교체.

```python
        settings = get_settings()
        try:
            self._api_key, self._model, self._base_url = resolve_user_llm(settings)
            self._llm_error = None
        except Exception as e:  # provider 해석 실패 — 설정은 안 깨고(비-LLM 엔드포인트 유지) stream 에서 노출.
            self._api_key = self._model = self._base_url = None
            self._llm_error = str(e)
```
`_default_streamer`·`_default_summarizer`·`_default_planner` 의 `LlmClient(api_key=self._api_key, model=self._model)` 를 `LlmClient(api_key=self._api_key, model=self._model, base_url=self._base_url)` 로.

`stream_sse` 의 기존 API 키 미설정 폴백(현재 `if not self._api_key:` → 비활성 delta)을 교체.

```python
        if self._llm_error:
            yield _sse({"type": "error", "message": f"상담 모델 설정 오류 — {self._llm_error}"})
            yield _sse({"type": "done"})
            return
```

- [ ] **Step 2: SelfModelExtractionService 배선**

`self_model_extraction_service.py` 상단에 `from core.llm.provider import resolve_user_llm` 추가. `__init__`(현재 25-27행) 교체.

```python
        settings = get_settings()
        try:
            self._api_key, self._model, self._base_url = resolve_user_llm(settings)
            self._llm_error = None
        except Exception as e:  # 해석 실패 — 추출 시 raise(폴백 없음). 구성 자체는 안 깨 테스트 주입을 허용.
            self._api_key = self._model = self._base_url = None
            self._llm_error = str(e)
```
`_default_extractor` 교체.

```python
    async def _default_extractor(self, messages: list[dict]) -> dict:
        if self._llm_error:
            raise RuntimeError(f"자기모델 추출 LLM 설정 오류 — {self._llm_error}")
        llm = LlmClient(api_key=self._api_key, model=self._model, base_url=self._base_url)
        return await llm.extract_self_model(messages)
```

- [ ] **Step 3: 기존 스위트 OpenAI 고정 + 회귀**

기본 provider=gemini 인데 dev/CI 엔 GEMINI_API_KEY 가 없어 resolve 가 실패한다. 실 LLM·FakeLLM 상담/추출 스위트가 OpenAI 로 돌게, 각 파일 상단(`os.environ.setdefault("SCHEDULER_ENABLED", "false")` 옆)에 한 줄 추가.

```python
os.environ.setdefault("USER_LLM_PROVIDER", "openai")
```
대상: `consult_service_test.py`·`consult_stream_test.py`·`consult_endpoint_test.py`·`self_model_extraction_test.py`. (openai provider → resolve 성공 → `_llm_error=None`·gpt-4o-mini 로 기존과 동일 동작.)

Run (각 FAIL=0): `python scripts/consult_service_test.py; python scripts/consult_stream_test.py; python scripts/consult_endpoint_test.py; python scripts/self_model_extraction_test.py; python scripts/consult_graph_test.py`

- [ ] **Step 4: 에러 표면화 테스트**

`consult_service_test.py` 에 케이스 추가 — provider=gemini·키 없음이면 stream_sse 가 error SSE 를 낸다(폴백 안 함). 환경을 임시로 바꿔 새 ConsultService 를 만든다.

```python
        # provider=gemini·GEMINI_API_KEY 없음 → stream_sse 가 error SSE(폴백 없음)
        import core.config.settings as _st
        _orig_env = (os.environ.get("USER_LLM_PROVIDER"), os.environ.get("GEMINI_API_KEY"))
        os.environ["USER_LLM_PROVIDER"] = "gemini"
        os.environ.pop("GEMINI_API_KEY", None)
        _st.get_settings.cache_clear()
        try:
            svc_err = ConsultService(s)
            sid_err = await svc_err.get_or_create_session(uid)
            evs = [json.loads(l[5:]) async for chunk in svc_err.stream_sse(uid, sid_err, "안녕")
                   for l in [chunk.strip()] if l.startswith("data:")]
            types = [e.get("type") for e in evs]
            check("gemini 키없음 → error SSE", "error" in types and "delta" not in types, str(types))
        finally:
            if _orig_env[0] is not None:
                os.environ["USER_LLM_PROVIDER"] = _orig_env[0]
            if _orig_env[1] is not None:
                os.environ["GEMINI_API_KEY"] = _orig_env[1]
            _st.get_settings.cache_clear()
```
(정확한 SSE 파싱·세션 헬퍼는 기존 테스트 스타일에 맞춰 조정. 핵심 단정 = error 있고 delta 없음. `get_settings`는 `@lru_cache`(settings.py:379)라 환경 변경 후 반드시 `get_settings.cache_clear()` — 위 코드대로.)

Run: `python scripts/consult_service_test.py`
Expected: `FAIL=0`(신규 에러표면 포함).

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/user_intelligence/hub/services/consult_service.py backend/domain/user_intelligence/hub/services/self_model_extraction_service.py backend/scripts/consult_service_test.py backend/scripts/consult_stream_test.py backend/scripts/consult_endpoint_test.py backend/scripts/self_model_extraction_test.py
git commit -m "feat(sp11): 상담·추출을 provider 해석으로 배선 + fail-loud 에러 표면화(폴백 없음)"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 (cwd `backend/`, 각 FAIL=0): `user_llm_resolve_test` · `consult_service_test` · `consult_stream_test` · `consult_endpoint_test` · `self_model_extraction_test` · `consult_graph_test` · `self_model_memory_test`.
- [ ] **라이브 verify(키 필요)** — `.env`에 `GEMINI_API_KEY` + `USER_LLM_PROVIDER=gemini` 넣고 Docker 재기동 후: 상담이 Gemini 2.5 Flash 로 응답(축 주도·반복 감소), 플래너·추출 `json_object` 동작, 키 빼면 error SSE. 자동 테스트로 대체 불가.
- [ ] 리뷰 게이트 — code-reviewer whole-branch → Codex `--base <시작 ref> --scope branch`.
