# 추천 설명 파서 — 닫힌 slug/id 검증·200자 클램프·실패 시 빈 리스트 (순수).

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _EXPLAIN_TEXT_MAX, _parse_recommend_explain

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


def run() -> int:
    slugs = ["ai-software", "bio-health"]
    ids = [10, 20]

    ok = json.dumps({
        "sync": [
            {"sector_slug": "ai-software", "text": " 관심 키워드와 정렬돼요. "},
            {"sector_slug": "unknown", "text": "버려야 함"},
            {"sector_slug": "bio-health", "text": ""},
        ],
        "chance": [
            {"opportunity_id": 10, "text": "포부와 맞닿아 있어요."},
            {"opportunity_id": 99, "text": "버려야 함"},
            {"opportunity_id": "20", "text": "문자열 id 버림"},
        ],
    }, ensure_ascii=False)
    r = _parse_recommend_explain(ok, slugs, ids)
    check("유효 sync 1건", r["sync"] == [{"sector_slug": "ai-software", "text": "관심 키워드와 정렬돼요."}], str(r["sync"]))
    check("유효 chance 1건", r["chance"] == [{"opportunity_id": 10, "text": "포부와 맞닿아 있어요."}], str(r["chance"]))

    # 중복 slug/id 는 첫 항목만
    dup = json.dumps({"sync": [
        {"sector_slug": "ai-software", "text": "첫째"},
        {"sector_slug": "ai-software", "text": "둘째"},
    ], "chance": []})
    check("중복 slug 첫 항목", _parse_recommend_explain(dup, slugs, ids)["sync"] == [{"sector_slug": "ai-software", "text": "첫째"}])

    # 200자 클램프
    long = json.dumps({"sync": [{"sector_slug": "ai-software", "text": "가" * 500}], "chance": []})
    r = _parse_recommend_explain(long, slugs, ids)
    check("클램프", len(r["sync"][0]["text"]) == _EXPLAIN_TEXT_MAX, str(len(r["sync"][0]["text"])))

    # 비JSON·비dict·None → 빈 결과
    check("비JSON", _parse_recommend_explain("응 안돼", slugs, ids) == {"sync": [], "chance": []})
    check("배열 루트", _parse_recommend_explain("[]", slugs, ids) == {"sync": [], "chance": []})
    check("None", _parse_recommend_explain(None, slugs, ids) == {"sync": [], "chance": []})

    # sync/chance 키 비list·항목 비dict 허용 처리
    weird = json.dumps({"sync": "x", "chance": [1, {"opportunity_id": 20, "text": "유효"}]})
    r = _parse_recommend_explain(weird, slugs, ids)
    check("비정형 관용", r == {"sync": [], "chance": [{"opportunity_id": 20, "text": "유효"}]}, str(r))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
