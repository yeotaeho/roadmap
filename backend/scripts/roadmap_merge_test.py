# 병합·WBS 검증 순수 함수 테스트 — done/active 보존·재삽입·시드 스킵 정책
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_pass = 0
_fail = 0


def check(name: str, cond: bool) -> None:
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"PASS {name}")
    else:
        _fail += 1
        print(f"FAIL {name}")


def q(key, parent, state="available", title=None, sort=0):
    return {
        "quest_key": key, "parent_key": parent, "title": title or key,
        "purpose": "", "difficulty": "입문", "keywords": [], "state": state,
        "sort_order": sort,
    }


def main() -> int:
    from domain.hrowth_journey.hub.services.roadmap_merge import (
        merge_roadmap,
        validate_wbs_tasks,
    )

    old = [
        q("root", None, "start"),
        q("q-a", "root", "done"),
        q("q-b", "root", "active"),
        q("q-c", "q-b", "available"),
        q("q-d", "root", "available"),  # 미진행·미참조 — 삭제 허용 대상.
        q("q-e", "q-d", "done"),        # done 인데 새 트리에서 사라짐 + 부모도 사라짐.
    ]
    new = {
        "title": "새 로드맵", "summary": "", "skill_pillars": [], "bridge_keywords": [],
        "quests": [
            q("root", None, "start"),
            q("q-a", "root", "available"),   # 에이전트가 상태를 되돌림 → done 보존돼야 함.
            q("q-b", "root", "locked"),      # active 보존돼야 함.
            q("q-new", "q-b", "done"),       # 새 key 의 done → available 강등.
            q("q-new2", "q-new", "start"),   # 비루트 start → available 강등.
        ],
    }
    merged = merge_roadmap(old, new, planner_keys={"q-c"})
    by_key = {x["quest_key"]: x for x in merged["quests"]}

    check("done 보존", by_key["q-a"]["state"] == "done")
    check("active 보존", by_key["q-b"]["state"] == "active")
    check("새 key done 강등", by_key["q-new"]["state"] == "available")
    check("비루트 start 강등", by_key["q-new2"]["state"] == "available")
    check("플래너 참조 재삽입", "q-c" in by_key)
    check("재삽입 부모 생존", by_key["q-c"]["parent_key"] == "q-b")
    check("사라진 done 재삽입", "q-e" in by_key)
    check("재삽입 부모 소실 시 루트", by_key["q-e"]["parent_key"] == "root")
    check("미진행 미참조 삭제", "q-d" not in by_key)
    roots = [x for x in merged["quests"] if x["parent_key"] is None]
    check("루트 1개 유지", len(roots) == 1)

    tasks = validate_wbs_tasks(
        [
            {"quest_key": "q-new", "title": "리서치", "description": "시장 조사", "estimated_days": 3},
            {"quest_key": "q-new", "title": "실습", "estimated_days": 200},   # est 범위 밖 → None.
            {"quest_key": "q-a", "title": "이미 done", "estimated_days": 2},   # done 스킵.
            {"quest_key": "q-c", "title": "이미 태스크 있음"},                  # existing 스킵.
            {"quest_key": "없는키", "title": "무효"},
            {"quest_key": "q-new2", "title": ""},                              # 빈 제목 스킵.
            {"quest_key": "q-new", "title": "3"}, {"quest_key": "q-new", "title": "4"},
            {"quest_key": "q-new", "title": "5"}, {"quest_key": "q-new", "title": "6"},  # 6번째 컷.
        ],
        merged["quests"],
        existing_task_keys={"q-c"},
    )
    keys = [t["quest_key"] for t in tasks]
    check("유효 시드만 통과", set(keys) == {"q-new"})
    check("퀘스트당 5개 상한", keys.count("q-new") == 5)
    check("est 범위 밖 None", tasks[1]["estimated_days"] is None)
    check("done 퀘스트 스킵", all(t["quest_key"] != "q-a" for t in tasks))

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
