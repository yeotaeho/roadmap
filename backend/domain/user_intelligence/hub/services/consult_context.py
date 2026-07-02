# 상담 대화 컨텍스트 순수 헬퍼 — 윈도우 분할·주입 메시지 조립


def select_to_summarize(total: int, window_n: int, threshold_t: int) -> bool:
    """총 메시지 수가 임계 초과면 오래된 메시지를 요약해야 한다."""
    return total > threshold_t


def split_history(messages: list[dict], window_n: int) -> tuple[list[dict], list[dict]]:
    """(older, recent) — 최근 window_n 개를 recent 로, 그 앞을 older 로 분리."""
    if window_n <= 0:
        return messages, []
    return messages[:-window_n], messages[-window_n:]


def build_llm_messages(
    system_content: str,
    context_summary: str | None,
    recent: list[dict],
    user_message: str,
) -> list[dict]:
    """LLM messages 배열 조립 — [system + (요약블록) + recent + 현재 user]."""
    out: list[dict] = [{"role": "system", "content": system_content}]
    if context_summary:
        out.append({"role": "system", "content": f"[이전 대화 요약]\n{context_summary}"})
    for m in recent:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    out.append({"role": "user", "content": user_message})
    return out
