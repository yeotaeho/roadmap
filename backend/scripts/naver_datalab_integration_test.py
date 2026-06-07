"""Naver DataLab 검색량 트렌드 API 통합 테스트 — 실제 API 호출.

실행:
  cd backend
  python scripts/naver_datalab_integration_test.py

테스트 항목:
  1. 단일 배치 (5그룹) API 호출 → HTTP 200 + ratio 데이터 확인
  2. 전체 수집 (7그룹 × 최근 4주) → DTO 개수·구조 검증
  3. 워터마크 skip — 이미 수집된 주는 DTO 생성 안 됨
  4. Backfill — start_date=12주 전 → 7×12=84 DTO 이상
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
for _p in [backend_dir / ".env", backend_dir.parent / ".env"]:
    if _p.exists():
        load_dotenv(_p)
        break

from domain.master.hub.services.collectors.economic.naver.naver_datalab_collector import (
    NaverDatalabCollector,
    NaverDatalabWatermark,
    _DATALAB_KEYWORD_GROUPS,
)

_KST = timezone(timedelta(hours=9))
_PASS = 0
_FAIL = 0


def ok(name: str) -> None:
    global _PASS
    _PASS += 1
    print(f"  [OK]   {name}")


def fail(name: str, detail: str = "") -> None:
    global _FAIL
    _FAIL += 1
    print(f"  [FAIL] {name}  -> {detail}")


async def test_single_batch(col: NaverDatalabCollector) -> None:
    print("\n[1] 단일 배치 5그룹 응답 구조 확인")
    import aiohttp, json
    headers = {
        "X-Naver-Client-Id": col._id,
        "X-Naver-Client-Secret": col._secret,
        "Content-Type": "application/json",
    }
    kst_now = datetime.now(tz=_KST)
    payload = {
        "startDate": (kst_now - timedelta(days=28)).strftime("%Y-%m-%d"),
        "endDate": kst_now.strftime("%Y-%m-%d"),
        "timeUnit": "week",
        "keywordGroups": [
            {"groupName": gname, "keywords": kws}
            for gname, kws in _DATALAB_KEYWORD_GROUPS[:5]
        ],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(
            "https://openapi.naver.com/v1/datalab/search",
            headers=headers, json=payload,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status == 200:
                ok(f"HTTP 200")
            else:
                fail("HTTP 200", f"status={r.status}")
                return
            data = await r.json()

    results = data.get("results", [])
    if len(results) == 5:
        ok("5그룹 응답")
    else:
        fail("5그룹 응답", f"got {len(results)}")

    for res in results:
        pts = res.get("data", [])
        gname = res.get("title", "?")
        if pts:
            latest = pts[-1]
            ok(f"[{gname}] {len(pts)}주 데이터, 최신 ratio={latest.get('ratio')}")
        else:
            fail(f"[{gname}] 데이터 없음")


async def test_collect_4weeks(col: NaverDatalabCollector) -> str | None:
    print("\n[2] 전체 수집 (7그룹 x 최근 4주)")
    dtos, stats = await col.collect(watermark=None)
    n_groups = len(_DATALAB_KEYWORD_GROUPS)
    print(f"     dtos={len(dtos)} batches={stats['batches_fetched']} errors={stats['errors']}")

    if len(dtos) >= n_groups:
        ok(f"DTO {len(dtos)}건 (그룹 수 {n_groups} 이상)")
    else:
        fail("DTO 건수 부족", f"{len(dtos)} < {n_groups}")

    if stats["errors"] == 0:
        ok("오류 0건")
    else:
        fail("오류 발생", str(stats["errors"]))

    if dtos:
        dto = dtos[0]
        ok(f"source_type={dto.source_type}") if dto.source_type == "DISCOURSE_NAVER_DATALAB" else fail("source_type")
        meta = dto.raw_metadata or {}
        if meta.get("ratio") is not None:
            ok(f"metadata.ratio={meta['ratio']}")
        else:
            fail("metadata.ratio 없음")
        if meta.get("week_start"):
            ok(f"metadata.week_start={meta['week_start']}")
        else:
            fail("metadata.week_start 없음")
        # 그룹별로 source_url이 다른지 확인
        urls = {d.source_url for d in dtos}
        if len(urls) == len(dtos):
            ok("source_url 전부 고유 (멱등성 보장)")
        else:
            fail("중복 source_url", f"{len(dtos)} dtos, {len(urls)} unique urls")

    return dtos[0].raw_metadata.get("week_start") if dtos else None


async def test_watermark_skip(col: NaverDatalabCollector, latest_week: str | None) -> None:
    print("\n[3] 워터마크 skip 검증")
    kst_now = datetime.now(tz=_KST)
    if not latest_week:
        ws = kst_now - timedelta(days=kst_now.weekday())
        latest_week = ws.strftime("%Y%m%d")

    wm = NaverDatalabWatermark(last_week_start=latest_week)
    dtos, stats = await col.collect(watermark=wm)

    skipped = stats.get("dtos_skipped_watermark", 0)
    created = stats.get("dtos_created", 0)

    if skipped > 0:
        ok(f"watermark({latest_week}) 이전 주 {skipped}건 skip")
    else:
        fail("skip 발생 안 함 — 최신 주 이후 새 데이터가 없으면 정상일 수 있음")

    print(f"     created={created} skipped={skipped}")


async def test_backfill_12weeks(col: NaverDatalabCollector) -> None:
    print("\n[4] Backfill 12주치")
    kst_now = datetime.now(tz=_KST)
    start_12w = (kst_now - timedelta(weeks=12)).strftime("%Y%m%d")
    dtos, stats = await col.collect(start_date=start_12w, watermark=None)
    n_groups = len(_DATALAB_KEYWORD_GROUPS)
    expected_min = n_groups * 10  # 12주 × 7그룹, 일부 주 데이터 없을 수 있어 10주분 기대

    print(f"     dtos={len(dtos)} (12주 x {n_groups}그룹 = 최대 {12*n_groups})")
    if len(dtos) >= expected_min:
        ok(f"Backfill DTO {len(dtos)}건 ({n_groups}그룹 x 10주 이상)")
    else:
        fail("Backfill DTO 부족", f"{len(dtos)} < {expected_min}")


async def main() -> int:
    print("=" * 68)
    print("Naver DataLab 검색량 트렌드 API 통합 테스트")
    print("=" * 68)

    cid = os.environ.get("NAVER_CLIENT_ID", "")
    csec = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not cid or not csec:
        print("\n[SKIP] NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 없음 - .env 확인")
        return 0

    print(f"CLIENT_ID: ...{cid[-6:]}")
    col = NaverDatalabCollector(cid, csec)

    await test_single_batch(col)
    latest_week = await test_collect_4weeks(col)
    await test_watermark_skip(col, latest_week)
    await test_backfill_12weeks(col)

    print("\n" + "=" * 68)
    print(f"결과: PASS={_PASS}  FAIL={_FAIL}")
    print("=" * 68)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
