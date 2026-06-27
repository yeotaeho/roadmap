# embed_service 배치 단위 commit 무네트워크 테스트

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

from domain.market_insight.hub.services.embed_service import (  # noqa: E402
    _BATCH,
    DocumentEmbedService,
    UserEmbedService,
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
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeDocRepo:
    def __init__(self, rows) -> None:
        self._rows = rows
        self.insert_calls = 0

    async def fetch_unembedded_docs(self, model, limit):
        return self._rows

    async def insert_doc_embedding(self, source_table, source_id, content, vec, model, sector_slug):
        self.insert_calls += 1


class _FakeUserRepo:
    def __init__(self, rows) -> None:
        self._rows = rows
        self.upsert_calls = 0

    async def fetch_unembedded_users(self, model, limit):
        return self._rows

    async def upsert_user_embedding(self, user_id, vec, version, model):
        self.upsert_calls += 1


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def _doc_row(i: int):
    return types.SimpleNamespace(
        content=f"doc content {i}",
        source_table="gap_issues",
        source_id=i,
        sector_slug="ai-data",
    )


def _user_row(i: int):
    return types.SimpleNamespace(
        user_id=i,
        target_job="개발자",
        interest_keywords=["AI", "데이터"],
    )


def test_doc_embed_batch_commit() -> None:
    # _BATCH=64 이고 70개면 배치 2개(64+6) → commit 2회
    n = _BATCH + 6
    svc = DocumentEmbedService.__new__(DocumentEmbedService)
    svc.session = _FakeSession()
    svc.repo = _FakeDocRepo([_doc_row(i) for i in range(n)])
    svc._llm = _FakeLlm()
    svc._model = "fake-embed"

    res = asyncio.run(svc.embed_documents(limit=1000))

    check(f"doc scanned={n}", res["scanned"] == n)
    check(f"doc embedded={n}", res["embedded"] == n)
    check(f"doc insert {n}회", svc.repo.insert_calls == n)
    check(f"doc commit=2(배치 {_BATCH}+{n-_BATCH})", svc.session.commits == 2)


def test_user_embed_batch_commit() -> None:
    n = _BATCH + 6
    svc = UserEmbedService.__new__(UserEmbedService)
    svc.session = _FakeSession()
    svc.repo = _FakeUserRepo([_user_row(i) for i in range(n)])
    svc._llm = _FakeLlm()
    svc._model = "fake-embed"

    res = asyncio.run(svc.embed_users(limit=1000))

    check(f"user scanned={n}", res["scanned"] == n)
    check(f"user embedded={n}", res["embedded"] == n)
    check(f"user upsert {n}회", svc.repo.upsert_calls == n)
    check(f"user commit=2(배치 {_BATCH}+{n-_BATCH})", svc.session.commits == 2)


def test_single_batch_commit_once() -> None:
    n = 10
    svc = DocumentEmbedService.__new__(DocumentEmbedService)
    svc.session = _FakeSession()
    svc.repo = _FakeDocRepo([_doc_row(i) for i in range(n)])
    svc._llm = _FakeLlm()
    svc._model = "fake-embed"

    asyncio.run(svc.embed_documents())

    check("단일 배치 commit=1", svc.session.commits == 1)


def main() -> int:
    test_doc_embed_batch_commit()
    test_user_embed_batch_commit()
    test_single_batch_commit_once()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
