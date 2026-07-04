# LLM 프로바이더 해석 — 상담·자기모델 추출용(openai | gemini). 폴백 없이 fail-loud.

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

_DEFAULT_MODEL = {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini"}


def resolve_user_llm(settings) -> tuple[str, str, str | None]:
    """상담·추출 LLM 설정 해석 → (api_key, model, base_url). 키 없음·미지 provider 는 ValueError(폴백 없음)."""
    provider = (getattr(settings, "user_llm_provider", None) or "gemini").lower()
    if provider not in _DEFAULT_MODEL:
        raise ValueError(f"알 수 없는 user_llm_provider 입니다: {provider}.")
    model = getattr(settings, "user_llm_model", "") or _DEFAULT_MODEL[provider]
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY 미설정 — Gemini provider 사용 불가.")
        return settings.gemini_api_key, model, GEMINI_BASE_URL
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY 미설정 — OpenAI provider 사용 불가.")
    return settings.openai_api_key, model, None
