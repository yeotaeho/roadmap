# Chance 추출 파서(_parse_chance)·매칭 스코어(score_match) 무네트워크 결정론적 테스트

from __future__ import annotations

import os
import sys

for _k, _v in dict(
    NEON_DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
    JWT_SECRET="x",
    NAVER_CLIENT_ID="x",
    NAVER_CLIENT_SECRET="x",
    NAVER_REDIRECT_URI="x",
).items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_chance  # noqa: E402
from domain.market_insight.hub.services.chance_match_service import score_match  # noqa: E402

SECTORS = ["ai-data", "fintech", "bio-health"]

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


def test_parse_valid() -> None:
    raw = (
        '{"sector_slug": "ai-data", "type": "공모전", "target": ["대학생", "취준생"],'
        ' "benefits": ["상금 500만원"], "qualifications": ["만 19세 이상"]}'
    )
    r = _parse_chance(raw, SECTORS)
    check("type 파싱", r["type"] == "공모전")
    check("sector 파싱", r["sector_slug"] == "ai-data")
    check("target 파싱", r["target"] == ["대학생", "취준생"])
    check("benefits 파싱", r["benefits"] == ["상금 500만원"])


def test_parse_abstain_and_sector() -> None:
    check("type null → 무귀속", _parse_chance('{"type": null}', SECTORS)["type"] is None)
    check("type 누락 → 무귀속", _parse_chance('{"target": ["x"]}', SECTORS)["type"] is None)
    r = _parse_chance('{"type": "채용", "sector_slug": "robotics"}', SECTORS)
    check("목록 외 섹터 → None(공고는 유효)", r["sector_slug"] is None and r["type"] == "채용")
    check("잘못된 JSON → 무귀속", _parse_chance("nope", SECTORS)["type"] is None)


def test_score_match() -> None:
    user_terms = ["인공지능", "데이터 분석가"]
    keywords = ["인공지능"]
    # 키워드 일치 → 40 + 1*20 = 60
    s1, r1 = score_match(user_terms, "인공지능 공모전 대학생 상금", None, keywords)
    check("키워드 1개 일치 → 60", s1 == 60)
    check("사유에 일치 키워드 포함", "인공지능" in r1)
    # 다중 일치
    s2, _ = score_match(user_terms, "인공지능 데이터 분석가 채용", None, keywords)
    check("키워드 2개 일치 → 80", s2 == 80)
    # 무일치 → 기본선 25
    s3, r3 = score_match(user_terms, "바이오 신약 임상", None, keywords)
    check("무일치 → 25", s3 == 25)
    # 섹터 가산
    s4, _ = score_match(["핀테크"], "결제 서비스", "fintech", ["핀테크", "fintech 관심"])
    check("섹터 직접 언급 가산(>25)", s4 > 25)
    # 점수 상한 100
    s5, _ = score_match(["a", "b", "c", "d"], "a b c d 공고", None, [])
    check("점수 상한 100", s5 == 100)


def main() -> int:
    for fn in (test_parse_valid, test_parse_abstain_and_sector, test_score_match):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
