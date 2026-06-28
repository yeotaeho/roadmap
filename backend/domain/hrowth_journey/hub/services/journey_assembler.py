# 퀘스트 트리 결정론 조립 — 평면 행 리스트 → 중첩 트리(DB 비의존 순수함수)

from __future__ import annotations


def _to_node(q: dict) -> dict:
    """평면 행 dict → 프론트 QuestTreeNode 모양(children 비움)."""
    return {
        "id": q["quest_key"],
        "title": q["title"],
        "purpose": q.get("purpose") or "",
        "difficulty": q["difficulty"],
        "keywords": q.get("keywords") or [],
        "state": q["state"],
        "children": [],
    }


def assemble_quest_tree(flat: list[dict]) -> dict | None:
    """평면 퀘스트 행 → 중첩 트리 루트 반환.

    각 행은 quest_key·parent_key·title·purpose·difficulty·keywords·state·sort_order 보유.
    parent_key 가 None 인 행이 루트. 형제는 sort_order(동률 시 quest_key) 오름차순.
    루트가 없으면 None.
    """
    if not flat:
        return None

    nodes = {q["quest_key"]: _to_node(q) for q in flat}
    order = {q["quest_key"]: (q.get("sort_order") or 0, q["quest_key"]) for q in flat}

    root_key: str | None = None
    for q in flat:
        parent = q.get("parent_key")
        if parent is None:
            root_key = q["quest_key"]
        elif parent in nodes:
            nodes[parent]["children"].append(nodes[q["quest_key"]])
        # 부모가 누락된 고아 노드는 트리에 매달지 않는다(드롭).

    if root_key is None:
        return None

    for node in nodes.values():
        node["children"].sort(key=lambda c: order[c["id"]])

    return nodes[root_key]
