# 코치 웹 tool 팩토리·셰이핑 단위 테스트(무DB·무네트워크) — 키 없으면 tool 제외·상한·출처 계약

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.spokes.agents.tools.web_tools import (
    WEB_TOOL_LABELS,
    build_web_tools,
    shape_page,
    shape_search_results,
)

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
    # 셰이핑 — 검색 결과
    data = {
        "results": [
            {"title": f"t{i}", "url": f"https://ex.com/{i}", "content": "x" * 500}
            for i in range(7)
        ]
        + [{"title": "no-url", "content": "y"}]
    }
    out = shape_search_results(data)
    check("검색 결과 최대 5건", len(out["results"]) == 5)
    check("스니펫 300자 상한", all(len(r["snippet"]) <= 300 for r in out["results"]))
    check("행마다 출처 url", all(r["url"].startswith("https://") for r in out["results"]))
    check("빈 응답 안전", shape_search_results({}) == {"results": []})

    # 셰이핑 — 페이지 본문 (중첩/평면 양쪽 방어)
    nested = {"result": {"markdown": "z" * 9000}}
    p1 = shape_page("https://ex.com", nested)
    check("본문 8000자 상한", len(p1["content"]) == 8000)
    check("잘림 표시", p1["truncated"] is True)
    check("url 포함", p1["url"] == "https://ex.com")
    flat = {"markdown": "짧은 본문."}
    p2 = shape_page("https://ex.com", flat)
    check("평면 응답 방어", p2["content"] == "짧은 본문." and p2["truncated"] is False)
    check("빈 응답 안전(페이지)", shape_page("https://ex.com", {})["content"] == "")

    # 팩토리 — 키 유무에 따른 tool 구성
    both = build_web_tools(SimpleNamespace(tavily_api_key="tk", watercrawl_api_key="wk"))
    names = {t.name for t in both}
    check("키 2개 → tool 2종", names == {"web_search", "fetch_url"}, str(names))
    check("전부 비동기", all(t.coroutine is not None for t in both))
    check("전부 설명 보유", all((t.description or "").strip() for t in both))

    none = build_web_tools(SimpleNamespace(tavily_api_key=None, watercrawl_api_key=None))
    check("키 없으면 빈 목록", none == [])

    only_search = build_web_tools(SimpleNamespace(tavily_api_key="tk", watercrawl_api_key=None))
    check("검색 키만 → web_search만", [t.name for t in only_search] == ["web_search"])

    # 라벨 계약
    check("라벨 전수", set(WEB_TOOL_LABELS.keys()) == {"web_search", "fetch_url"})
    check("라벨 한국어", all(any("가" <= ch <= "힣" for ch in v) for v in WEB_TOOL_LABELS.values()))

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
