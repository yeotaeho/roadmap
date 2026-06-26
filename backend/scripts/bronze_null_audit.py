# Bronze 계층 NULL·결측 비율 측정 — 수집 손실 우선순위 진단 (일회성 측정)

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Windows cp949 콘솔에서 한글·em dash 출력 깨짐 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "  -  "
    return f"{100.0 * n / total:5.1f}%"


# (테이블, [NULL/빈문자 측정 컬럼], [텍스트 길이 측정 컬럼], [metadata 본문 키])
TABLES: tuple[tuple[str, list[str], list[str], list[str]], ...] = (
    (
        "raw_economic_data",
        ["source_url", "investor_name", "target_company_or_fund",
         "investment_amount", "raw_metadata", "published_at"],
        [],
        ["content_text", "body_text"],
    ),
    (
        "raw_discourse_data",
        ["source_url", "author_or_publisher", "content_body",
         "raw_metadata", "published_at"],
        ["content_body"],
        [],
    ),
    (
        "raw_innovation_data",
        ["source_url", "author_or_assignee", "abstract_text",
         "raw_metadata", "published_at"],
        ["abstract_text"],
        [],
    ),
    (
        "raw_opportunity_data",
        ["source_url", "host_name", "raw_content",
         "raw_metadata", "published_at", "deadline_at"],
        ["raw_content"],
        [],
    ),
    (
        "raw_people_data",
        ["source_url", "search_volume_or_count", "raw_metadata", "reference_date"],
        [],
        [],
    ),
    (
        "raw_market_timeseries",
        ["open_price", "high_price", "low_price", "turnover_amount"],
        [],
        [],
    ),
    (
        "verified_company_master",
        ["business_number", "corp_number", "ceo_name", "certification_type",
         "certification_date", "industry_sector", "establishment_date"],
        [],
        [],
    ),
)

# 텍스트형 컬럼(빈 문자열도 결측으로 카운트)
_TEXT_COLS = {
    "source_url", "investor_name", "target_company_or_fund", "author_or_publisher",
    "content_body", "author_or_assignee", "abstract_text", "host_name", "raw_content",
    "business_number", "corp_number", "ceo_name", "certification_type",
    "industry_sector",
}


async def _table_exists(session, table: str) -> bool:
    row = await session.execute(
        text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}
    )
    return row.scalar() is not None


async def audit_table(
    session, table: str, cols: list[str], len_cols: list[str], meta_keys: list[str]
) -> None:
    if not await _table_exists(session, table):
        print(f"\n### {table} — (테이블 없음, 스킵)")
        return

    total = (await session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar() or 0
    print(f"\n{'=' * 72}")
    print(f"### {table} — 전체 {total:,}건")
    print(f"{'=' * 72}")
    if total == 0:
        print("  (행 없음)")
        return

    # 컬럼별 NULL(+빈문자열) 결측률
    sel = [f"COUNT(*) FILTER (WHERE {c} IS NULL) AS {c}__null" for c in cols]
    for c in cols:
        if c in _TEXT_COLS:
            sel.append(f"COUNT(*) FILTER (WHERE {c} = '') AS {c}__empty")
    row = (await session.execute(
        text(f"SELECT {', '.join(sel)} FROM {table}")
    )).mappings().first()

    print(f"\n  {'컬럼':<26}{'NULL':>10}{'빈문자':>10}{'결측합계':>12}")
    print(f"  {'-' * 56}")
    for c in cols:
        n_null = row[f"{c}__null"] or 0
        n_empty = (row.get(f"{c}__empty") or 0) if c in _TEXT_COLS else 0
        miss = n_null + n_empty
        print(f"  {c:<26}{_pct(n_null, total):>10}"
              f"{(_pct(n_empty, total) if c in _TEXT_COLS else '  -  '):>10}"
              f"{_pct(miss, total):>12}")

    # 텍스트 본문 길이 분포
    for c in len_cols:
        r = (await session.execute(text(
            f"SELECT AVG(LENGTH({c}))::int AS avg, "
            f"MIN(LENGTH({c})) AS min, MAX(LENGTH({c})) AS max, "
            f"COUNT(*) FILTER (WHERE LENGTH({c}) < 200) AS short "
            f"FROM {table} WHERE {c} IS NOT NULL AND {c} <> ''"
        ))).mappings().first()
        if r and r["avg"] is not None:
            print(f"\n  [{c}] 본문 길이 — 평균 {r['avg']:,}자 / 최소 {r['min']} / "
                  f"최대 {r['max']:,} / 200자 미만 {r['short']:,}건"
                  f"({_pct(r['short'], total)})")

    # raw_metadata 내 본문 키 존재율(= 본문 보강 성공률)
    for k in meta_keys:
        n = (await session.execute(text(
            f"SELECT COUNT(*) FROM {table} WHERE raw_metadata ->> :k IS NOT NULL"
        ), {"k": k})).scalar() or 0
        print(f"  [raw_metadata->>'{k}'] 존재: {n:,}건 ({_pct(n, total)})")

    # source_type별 건수 (상위 12)
    if "source_type" in await _columns(session, table):
        rows = (await session.execute(text(
            f"SELECT source_type, COUNT(*) AS c FROM {table} "
            f"GROUP BY source_type ORDER BY c DESC LIMIT 12"
        ))).all()
        print(f"\n  source_type 분포(상위 12):")
        for st, c in rows:
            print(f"    {st:<28}{c:>8,}건")


async def _columns(session, table: str) -> set[str]:
    rows = (await session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = :t"
    ), {"t": table})).all()
    return {r[0] for r in rows}


async def discourse_by_publisher(session) -> None:
    """담론 content_body 결측을 매체별로 — '데이터 있는데 못 가져옴'의 핵심."""
    if not await _table_exists(session, "raw_discourse_data"):
        return
    rows = (await session.execute(text(
        """
        SELECT COALESCE(author_or_publisher, '(NULL)') AS pub,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE content_body IS NULL OR content_body = '') AS missing,
               AVG(LENGTH(content_body))::int AS avg_len
        FROM raw_discourse_data
        GROUP BY author_or_publisher
        ORDER BY total DESC
        LIMIT 15
        """
    ))).mappings().all()
    if not rows:
        return
    print(f"\n{'=' * 72}")
    print("### raw_discourse_data — 매체별 content_body 결측 (본문 누락 추적)")
    print(f"{'=' * 72}")
    print(f"  {'매체':<22}{'건수':>8}{'본문결측':>12}{'평균길이':>10}")
    print(f"  {'-' * 52}")
    for r in rows:
        print(f"  {r['pub']:<22}{r['total']:>8,}"
              f"{_pct(r['missing'], r['total']):>12}"
              f"{(str(r['avg_len']) + '자' if r['avg_len'] is not None else '-'):>10}")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        print("\n" + "#" * 72)
        print("# Bronze 계층 결측 측정 리포트")
        print("#" * 72)
        for table, cols, len_cols, meta_keys in TABLES:
            try:
                await audit_table(session, table, cols, len_cols, meta_keys)
            except Exception as e:  # noqa: BLE001
                print(f"\n[ERROR] {table}: {e}")
        try:
            await discourse_by_publisher(session)
        except Exception as e:  # noqa: BLE001
            print(f"\n[ERROR] discourse_by_publisher: {e}")
        print("\n[완료]\n")


if __name__ == "__main__":
    asyncio.run(main())
