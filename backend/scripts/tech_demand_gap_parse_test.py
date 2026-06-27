# KIAT 수요기술 Gap 추출 파서 무네트워크 회귀 테스트

from __future__ import annotations

import json
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

from core.llm.client import _parse_tech_demand_gap  # noqa: E402

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


def test_valid() -> None:
    raw = json.dumps({
        "problem": "기업이 엣지 AI 경량화 인력을 못 구한다",
        "opportunity": "온디바이스 모델 최적화 역량을 키우면 진입할 수 있다",
        "detail": "수요는 크나 공급이 부족하다. 개인 학습으로 진입 가능하다.",
        "stakeholders": ["AI 스타트업", "디바이스 제조사"],
        "next_actions": ["경량화 프레임워크 학습", "포트폴리오 구축"],
        "youth_fit": 0.8,
    })
    r = _parse_tech_demand_gap(raw)
    check("valid problem", r["problem"].startswith("기업이"))
    check("valid youth_fit", r["youth_fit"] == 0.8)
    check("valid stakeholders len", len(r["stakeholders"]) == 2)


def test_missing_opportunity_voids() -> None:
    raw = json.dumps({"problem": "문제만 있음", "opportunity": None, "youth_fit": 0.9})
    r = _parse_tech_demand_gap(raw)
    check("void problem None", r["problem"] is None)
    check("void youth_fit 0", r["youth_fit"] == 0.0)


def test_youth_fit_clamped() -> None:
    raw = json.dumps({"problem": "p", "opportunity": "o", "youth_fit": 5})
    check("clamp high", _parse_tech_demand_gap(raw)["youth_fit"] == 1.0)
    raw2 = json.dumps({"problem": "p", "opportunity": "o", "youth_fit": "bad"})
    check("bad youth_fit -> 0", _parse_tech_demand_gap(raw2)["youth_fit"] == 0.0)


def test_malformed() -> None:
    check("none raw", _parse_tech_demand_gap(None)["problem"] is None)
    check("bad json", _parse_tech_demand_gap("{not json")["problem"] is None)


if __name__ == "__main__":
    test_valid()
    test_missing_opportunity_voids()
    test_youth_fit_clamped()
    test_malformed()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
