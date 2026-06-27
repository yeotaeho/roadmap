# investment_flow_service 청크 단위 upsert·commit 무네트워크 테스트

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

from domain.market_insight.hub.services.investment_flow_service import (  # noqa: E402
    REFINE_CHUNK,
    InvestmentFlowRefineService,
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
        title=f"스타트업 {i} 시리즈A 50억 투자 유치",
        company_hint=f"Company{i}",
        ref_date="2026-01-01",
        raw_id=i,
    )


class _FakeLlm:
    async def extract_investment(self, text: str) -> dict:
        return {
            "amount_krw": 5_000_000_000,
            "currency": "KRW",
            "series": "A",
            "company": "Test Corp",
        }


class _FakeRepo:
    def __init__(self, rows) -> None:
        self._rows = rows
        self.upsert_calls = 0

    async def fetch_unprocessed(self, pv, window, limit):
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
    svc = InvestmentFlowRefineService.__new__(InvestmentFlowRefineService)
    svc.session = _FakeSession()
    svc.repo = _FakeRepo([_row(i) for i in range(n)])
    svc._llm = _FakeLlm()
    svc._model = "fake"

    res = asyncio.run(svc.refine_and_serve(window_days=90, limit=1000))

    check("scanned=60", res["scanned"] == 60)
    check("extracted=60", res["extracted"] == 60)
    check("upsert_silver 60회", svc.repo.upsert_calls == 60)
    # 60건 / 25 = 2청크 중간 + 1회(최종) = 3회
    check(f"commit >= 3(청크 {REFINE_CHUNK}×2 + 최종)", svc.session.commits >= 3)


def test_small_batch_still_commits() -> None:
    n = 10
    svc = InvestmentFlowRefineService.__new__(InvestmentFlowRefineService)
    svc.session = _FakeSession()
    svc.repo = _FakeRepo([_row(i) for i in range(n)])
    svc._llm = _FakeLlm()
    svc._model = "fake"

    asyncio.run(svc.refine_and_serve())

    check("소량 배치 commit >= 1", svc.session.commits >= 1)


def main() -> int:
    test_chunked_commit()
    test_small_batch_still_commits()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
