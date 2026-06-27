# GapProjectionService 단일 사영 무네트워크 테스트

from __future__ import annotations

import asyncio
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

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from domain.market_insight.hub.services.gap_projection_service import (  # noqa: E402
    DISCOURSE_PV,
    TECH_DEMAND_PV,
    GapProjectionService,
)

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


class _FakeRepo:
    def __init__(self) -> None:
        self.calls: list = []

    async def project_to_gold(self, disc_pv, td_pv, fit_min) -> int:
        self.calls.append((disc_pv, td_pv, fit_min))
        return 7


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def test_single_projection() -> None:
    svc = GapProjectionService.__new__(GapProjectionService)
    svc.session = _FakeSession()
    svc.repo = _FakeRepo()
    svc._fit_min = 0.5

    res = asyncio.run(svc.project_and_serve())

    check("project_to_gold 정확히 1회", len(svc.repo.calls) == 1)
    check("두 소스 pv 전달", svc.repo.calls[0][:2] == (DISCOURSE_PV, TECH_DEMAND_PV))
    check("fit_min 전달", svc.repo.calls[0][2] == 0.5)
    check("issues 반환", res["issues"] == 7)
    check("commit >= 1", svc.session.commits >= 1)


def main() -> int:
    test_single_projection()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
