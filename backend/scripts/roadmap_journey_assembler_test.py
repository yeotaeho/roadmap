# 퀘스트 트리 순수 조립 함수 무DB 검증 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.hrowth_journey.hub.services.journey_assembler import assemble_quest_tree  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def _q(key, parent, order=0, **kw):
    base = {
        "quest_key": key,
        "parent_key": parent,
        "title": kw.get("title", key),
        "purpose": kw.get("purpose", ""),
        "difficulty": kw.get("difficulty", "입문"),
        "keywords": kw.get("keywords", []),
        "state": kw.get("state", "available"),
        "sort_order": order,
    }
    return base


def test_empty() -> None:
    check("빈 입력 → None", assemble_quest_tree([]) is None)


def test_no_root() -> None:
    flat = [_q("a", "missing")]  # 루트(parent None) 없음
    check("루트 없으면 None", assemble_quest_tree(flat) is None)


def test_single_root() -> None:
    tree = assemble_quest_tree([_q("root", None, title="시작")])
    check("단일 루트 id", tree["id"] == "root")
    check("단일 루트 children 빈 리스트", tree["children"] == [])
    check("필드 매핑(title)", tree["title"] == "시작")


def test_nesting_and_sort() -> None:
    flat = [
        _q("root", None),
        _q("b", "root", order=2),
        _q("a", "root", order=1),
        _q("a1", "a", order=1),
    ]
    tree = assemble_quest_tree(flat)
    top = [c["id"] for c in tree["children"]]
    check("형제 sort_order 오름차순(a 먼저)", top == ["a", "b"])
    a = next(c for c in tree["children"] if c["id"] == "a")
    check("손자 매달림(a→a1)", [c["id"] for c in a["children"]] == ["a1"])


def test_sibling_tie_by_key() -> None:
    flat = [_q("root", None), _q("y", "root", order=0), _q("x", "root", order=0)]
    tree = assemble_quest_tree(flat)
    check("동률 sort_order → quest_key 사전순(x 먼저)", [c["id"] for c in tree["children"]] == ["x", "y"])


def test_orphan_dropped() -> None:
    flat = [_q("root", None), _q("ok", "root"), _q("ghost", "nonexistent")]
    tree = assemble_quest_tree(flat)
    check("고아 노드는 트리에서 드롭", [c["id"] for c in tree["children"]] == ["ok"])


def test_state_keywords_preserved() -> None:
    flat = [_q("root", None, state="start", keywords=["현재", "간극"], difficulty="중급")]
    tree = assemble_quest_tree(flat)
    check("state 보존", tree["state"] == "start")
    check("keywords 보존", tree["keywords"] == ["현재", "간극"])
    check("difficulty 보존", tree["difficulty"] == "중급")


def main() -> int:
    test_empty()
    test_no_root()
    test_single_root()
    test_nesting_and_sort()
    test_sibling_tie_by_key()
    test_orphan_dropped()
    test_state_keywords_preserved()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
