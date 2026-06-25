# trending_keywords 순수 조립 함수 무DB 검증 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.keyword_trends import assemble_keywords  # noqa: E402

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


def test_cloud_freq_desc() -> None:
    out = assemble_keywords({"LLM": 18, "RAG": 12, "Agent": 5}, {}, cloud_limit=2)
    cloud = out["cloud"]
    check("cloud 빈도 내림차순 + limit", [c["keyword"] for c in cloud] == ["LLM", "RAG"])
    check("cloud weight=df", cloud[0]["weight"] == 18)
    check("cloud rank 1부터", cloud[0]["rank"] == 1 and cloud[1]["rank"] == 2)


def test_cloud_tie_alpha() -> None:
    out = assemble_keywords({"B": 5, "A": 5}, {})
    check("cloud 동률 사전순(A 먼저)", [c["keyword"] for c in out["cloud"]] == ["A", "B"])


def test_ticker_delta_and_rising_only() -> None:
    recent = {"RAG": 10, "flat": 8, "down": 6}
    prior = {"RAG": 5, "flat": 8, "down": 8}
    out = assemble_keywords(recent, prior)
    tick = {t["keyword"]: t for t in out["ticker"]}
    check("상승 RAG delta=100·라벨", tick["RAG"]["delta_pct"] == 100 and tick["RAG"]["value_label"] == "+100%")
    check("보합(flat, delta 0) 제외", "flat" not in tick)
    check("하락(down) 제외", "down" not in tick)


def test_ticker_new() -> None:
    out = assemble_keywords({"NEW": 3}, {})
    t = out["ticker"][0]
    check("신규 delta null", t["delta_pct"] is None)
    check("신규 라벨", t["value_label"] == "신규")


def test_ticker_min_recent() -> None:
    out = assemble_keywords({"low": 1, "ok": 2}, {})  # ticker_min_recent 기본 2
    slugs = [t["keyword"] for t in out["ticker"]]
    check("min_recent 미만(low=1) 제외", "low" not in slugs)
    check("min_recent 충족(ok=2) 포함", "ok" in slugs)


def test_ticker_sort_new_first() -> None:
    out = assemble_keywords({"N": 5, "RAG": 10}, {"RAG": 5})
    order = [t["keyword"] for t in out["ticker"]]
    check("신규(N)가 상승(RAG)보다 앞", order[0] == "N")
    check("ticker rank 1부터", out["ticker"][0]["rank"] == 1)


def test_empty() -> None:
    out = assemble_keywords({}, {})
    check("전무 cloud []", out["cloud"] == [])
    check("전무 ticker []", out["ticker"] == [])


def main() -> int:
    test_cloud_freq_desc()
    test_cloud_tie_alpha()
    test_ticker_delta_and_rising_only()
    test_ticker_new()
    test_ticker_min_recent()
    test_ticker_sort_new_first()
    test_empty()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
