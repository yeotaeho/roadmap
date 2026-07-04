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

    from core.llm.client import LlmClient
    c1 = LlmClient(api_key="x", model="m", base_url="https://ex.test/v1/")
    check("base_url 전달", str(c1._client.base_url).startswith("https://ex.test"), str(c1._client.base_url))
    c2 = LlmClient(api_key="x", model="m")
    check("base_url None 기본 OpenAI", "openai.com" in str(c2._client.base_url), str(c2._client.base_url))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
