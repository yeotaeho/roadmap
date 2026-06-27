# gap_refine_service 청크 단위 upsert·commit 무네트워크 테스트

from __future__ import annotations

import asyncio
import os
import sys
import types

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

from domain.market_insight.hub.services.gap_refine_service import (  # noqa: E402
    REFINE_CHUNK,
    GapRefineService,
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


def _row(i: int):
    return types.SimpleNamespace(
        body=f"gap body {i}",
        sector_slug="ai-data",
        ref_date="2026-01-01",
        raw_id=i,
    )


class _FakeLlm:
    async def extract_gap(self, text: str) -> dict:
        return {
            "problem": "test problem",
            "opportunity": "test opp",
            "detail": "detail",
            "stakeholders": [],
            "next_actions": [],
        }


class _FakeRepo:
    def __init__(self, rows) -> None:
        self._rows = rows
        self.upsert_calls = 0
        self.gold_calls = 0

    async def fetch_unprocessed(self, pv, conf_min, window, limit):
        return self._rows

    async def upsert_silver(self, payload: dict) -> None:
        self.upsert_calls += 1


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def test_chunked_commit() -> None:
    n = 60
    svc = GapRefineService.__new__(GapRefineService)
    svc.session = _FakeSession()
    svc.repo = _FakeRepo([_row(i) for i in range(n)])
    svc._llm = _FakeLlm()
    svc._model = "fake"
    svc._conf_min = 0.0

    res = asyncio.run(svc.refine_and_serve(window_days=90, limit=1000))

    check("scanned=60", res["scanned"] == 60)
    check("gaps=60", res["gaps"] == 60)
    check("skipped=0", res["skipped"] == 0)
    check("upsert_silver 60회", svc.repo.upsert_calls == 60)
    check("project_to_gold 0회(refine 는 사영 안 함)", svc.repo.gold_calls == 0)
    # 60건 / 25 = 2청크 중간 + 1회(잔여 flush) = 3회
    check(f"commit >= 3(청크 {REFINE_CHUNK}×2 + 잔여 flush)", svc.session.commits >= 3)


def test_small_batch_still_commits() -> None:
    n = 10
    svc = GapRefineService.__new__(GapRefineService)
    svc.session = _FakeSession()
    svc.repo = _FakeRepo([_row(i) for i in range(n)])
    svc._llm = _FakeLlm()
    svc._model = "fake"
    svc._conf_min = 0.0

    asyncio.run(svc.refine_and_serve())

    check("소량 배치 commit >= 1", svc.session.commits >= 1)


def main() -> int:
    test_chunked_commit()
    test_small_batch_still_commits()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
