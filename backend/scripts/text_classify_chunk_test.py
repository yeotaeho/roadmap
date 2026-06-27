# text_sector_classify_service 청크 단위 upsert·commit 무네트워크 테스트

from __future__ import annotations

import asyncio
import os
import sys

# settings 로드용 최소 환경값(.env 가 나머지 제공). DB·LLM 미접속 — fake 주입.
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

from domain.market_insight.hub.services.text_sector_classify_service import (  # noqa: E402
    CLASSIFY_CHUNK,
    TextSectorClassifyService,
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


class _FakeLlm:
    async def classify_sector(self, text: str, sectors: list[str]) -> dict:
        return {"sector_slug": "ai-data", "confidence": 0.9}


class _FakeRepo:
    def __init__(self, rows_by_table: dict[str, list[tuple[int, str]]]) -> None:
        self._rows = rows_by_table
        self.upsert_calls: list[int] = []

    async def fetch_unclassified_text_rows(self, table_ref, pv, window, limit):
        return self._rows.get(table_ref, [])

    async def upsert_text_sector_class(self, payload: list[dict]) -> int:
        self.upsert_calls.append(len(payload))
        return len(payload)


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def test_chunked_upsert_commit() -> None:
    # __init__(LlmClient·Repo 생성) 우회하고 fake 주입.
    svc = TextSectorClassifyService.__new__(TextSectorClassifyService)
    svc.session = _FakeSession()
    svc.repo = _FakeRepo({"raw_economic_data": [(i, f"body {i}") for i in range(60)]})
    svc._llm = _FakeLlm()
    svc._model = "fake"

    res = asyncio.run(svc.classify_unclassified(window_days=90, limit=1000))

    check("scanned=60", res["scanned"] == 60)
    check("classified=60(fake 전건 분류)", res["classified"] == 60)
    check(
        f"upsert 청크 크기 <= {CLASSIFY_CHUNK}",
        bool(svc.repo.upsert_calls) and all(c <= CLASSIFY_CHUNK for c in svc.repo.upsert_calls),
    )
    # 60건 / 25 = 3청크(25+25+10) — LLM idle 구간을 청크로 분할해 연결 수명 초과 방지.
    check("60건 → upsert 3회", len(svc.repo.upsert_calls) == 3)
    check("commit 청크마다(>=3)", svc.session.commits >= 3)


def main() -> int:
    test_chunked_upsert_commit()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
