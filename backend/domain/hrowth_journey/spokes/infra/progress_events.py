# 딥 에이전트 스트림 청크 → 시맨틱 진행 이벤트 매핑(무네트워크 순수 함수)
from __future__ import annotations

STAGE_PERCENT = {
    "start": 5,
    "market_analyst": 30,
    "opportunity_scout": 50,
    "quest_designer": 80,
    "saving": 95,
    "done": 100,
}

STAGE_LABEL = {
    "start": "생성 준비",
    "market_analyst": "시장 분석",
    "opportunity_scout": "기회 조사",
    "quest_designer": "퀘스트 설계",
    "saving": "검증·저장",
    "done": "완료",
}


def _todos_of(update: dict) -> list | None:
    todos = update.get("todos")
    if not isinstance(todos, list):
        return None
    out = []
    for t in todos:
        if isinstance(t, dict) and t.get("content"):
            out.append({"content": str(t["content"])[:120], "status": t.get("status") or ""})
    return out


def map_agent_event(mode: str, payload) -> list[dict]:
    """astream(stream_mode=["updates","custom"]) 청크 → 시맨틱 이벤트 목록.

    반환 kind: todos(할 일 갱신) / subagent_start / subagent_end. 미해당 청크는 [].
    """
    events: list[dict] = []
    if mode != "updates" or not isinstance(payload, dict):
        return events
    for update in payload.values():
        if not isinstance(update, dict):
            continue
        todos = _todos_of(update)
        if todos is not None:
            events.append({"kind": "todos", "todos": todos})
        for msg in update.get("messages") or []:
            for tc in getattr(msg, "tool_calls", None) or []:
                if tc.get("name") == "task":
                    sub = (tc.get("args") or {}).get("subagent_type") or "unknown"
                    events.append({"kind": "subagent_start", "name": sub})
            if getattr(msg, "type", None) == "tool" and getattr(msg, "name", None) == "task":
                events.append({"kind": "subagent_end"})
    return events
