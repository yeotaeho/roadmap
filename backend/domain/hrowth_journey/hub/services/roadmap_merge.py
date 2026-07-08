# 로드맵 진행 보존 병합 — done/active·플래너 연결 생존을 코드로 강제(무네트워크 순수 함수)
from __future__ import annotations

_PRESERVED_STATES = {"done", "active"}
_VALID_REINSERT_STATES = {"done", "active", "available", "locked"}
_MAX_TASKS_PER_QUEST = 5
_MAX_EST_DAYS = 90


def merge_roadmap(old_quests: list[dict], new_roadmap: dict, planner_keys: set[str]) -> dict:
    """에이전트 산출을 기존 트리와 병합한다. new_roadmap 은 _parse_roadmap 검증 통과본.

    규칙:
    1. 살아남은 key 가 기존 done/active 면 state 무조건 보존(에이전트 제안 무시).
    2. 새 key 는 done 금지(available 강등). start 는 루트만(비루트 start 는 available 강등).
    3. 사라진 key 중 done 또는 플래너 참조 퀘스트는 자동 재삽입(원 부모 생존 시 그 아래, 아니면 새 루트 아래).
       재삽입 노드가 옛 루트(parent None)였으면 새 루트 아래로 편입, start 상태는 done 으로 강등.
    4. 사라진 미진행·미참조 퀘스트는 삭제 허용.
    """
    old_by_key = {q["quest_key"]: q for q in old_quests}
    new_quests = [dict(q) for q in new_roadmap["quests"]]
    new_keys = {q["quest_key"] for q in new_quests}
    root_key = next(q["quest_key"] for q in new_quests if q["parent_key"] is None)

    for q in new_quests:
        old = old_by_key.get(q["quest_key"])
        if old is not None and old["state"] in _PRESERVED_STATES:
            q["state"] = old["state"]
        elif old is None and q["state"] == "done":
            q["state"] = "available"
        if q["state"] == "start" and q["parent_key"] is not None:
            q["state"] = "available"

    reinsert_keys = {
        key
        for key, old in old_by_key.items()
        if key not in new_keys and (old["state"] == "done" or key in planner_keys)
    }
    alive = new_keys | reinsert_keys

    reinserted = []
    for key, old in old_by_key.items():
        if key in new_keys:
            continue
        if old["state"] != "done" and key not in planner_keys:
            continue  # 미진행·미참조 — 삭제 허용.
        parent = old.get("parent_key")
        if parent is None or parent not in alive:
            parent = root_key
        state = old["state"] if old["state"] in _VALID_REINSERT_STATES else "done"
        reinserted.append(
            {
                "quest_key": key,
                "parent_key": parent,
                "title": old["title"],
                "purpose": old.get("purpose") or "",
                "difficulty": old.get("difficulty") or "입문",
                "keywords": old.get("keywords") or [],
                "state": state,
                "sort_order": 900 + len(reinserted),  # 뒤쪽 배치 — 형제 정렬 안정.
            }
        )

    return {**new_roadmap, "quests": new_quests + reinserted}


def validate_wbs_tasks(
    raw_tasks, merged_quests: list[dict], existing_task_keys: set[str]
) -> list[dict]:
    """WBS 초안 검증 — 병합 트리에 있는 미완료·태스크 없는 퀘스트에만, 퀘스트당 최대 5개."""
    if not isinstance(raw_tasks, list):
        return []
    valid_keys = {q["quest_key"] for q in merged_quests}
    done_keys = {q["quest_key"] for q in merged_quests if q["state"] == "done"}
    out: list[dict] = []
    per_quest: dict[str, int] = {}
    for t in raw_tasks:
        if not isinstance(t, dict):
            continue
        key = t.get("quest_key")
        title = t.get("title")
        if not isinstance(key, str) or key not in valid_keys or key in done_keys:
            continue
        if key in existing_task_keys:
            continue  # 이미 태스크가 있는 퀘스트는 시드 스킵(소스 불문).
        if not isinstance(title, str) or not title.strip():
            continue
        if per_quest.get(key, 0) >= _MAX_TASKS_PER_QUEST:
            continue
        est = t.get("estimated_days")
        if not isinstance(est, int) or not (1 <= est <= _MAX_EST_DAYS):
            est = None
        desc = t.get("description")
        out.append(
            {
                "quest_key": key,
                "title": title.strip()[:200],
                "description": desc.strip()[:2000] if isinstance(desc, str) and desc.strip() else None,
                "estimated_days": est,
            }
        )
        per_quest[key] = per_quest.get(key, 0) + 1
    return out
