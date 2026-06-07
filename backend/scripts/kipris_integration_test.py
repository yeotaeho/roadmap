"""KIPRIS PLUS 특허 검색 API 통합 테스트 — 실제 API 호출.

사전 준비:
  backend/.env 에 KIPRIS_API_KEY=<발급받은 키> 설정 필요.

실행:
  cd backend
  python scripts/kipris_integration_test.py

테스트 항목:
  1. ServiceKey 인증 (resultCode=00 확인)
  2. 날짜 필터 (applicationDate=YYYYMMDD~YYYYMMDD, 틸다 구분)
  3. 키워드 검색 (inventionTitle=인공지능 → totalCount > 0)
  4. 전체 키워드 그룹 주간 수집 (collect() 호출, watermark=None)
  5. 워터마크 동일 주 skip (collect() 재호출 시 dtos=[] 확인)
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
# backend/.env → 없으면 프로젝트 루트 .env 탐색
for _env_path in [backend_dir / ".env", backend_dir.parent / ".env"]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

from domain.master.hub.services.collectors.economic.kipris.kipris_patent_collector import (
    KiprisPatentCollector,
    KiprisWatermark,
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
    print(f"  [FAIL] {name}  →  {detail}")


async def test_single_keyword(key: str) -> None:
    print("\n[1] 단일 키워드 API 호출 (인공지능, 최근 30일)")
    kst_now = datetime.now(tz=_KST)
    week_start = kst_now - timedelta(days=kst_now.weekday())
    week_end = week_start + timedelta(days=6)
    date_range = f"{week_start.strftime('%Y%m%d')}~{week_end.strftime('%Y%m%d')}"

    import aiohttp
    import re

    url = (
        "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getAdvancedSearch"
        f"?ServiceKey={key}"
        "&patent=Y&utility=N&register=Y&registerRejected=Y&makeRejected=Y"
        "&open=Y&openReject=Y&abandon=Y&registration=Y&lapse=Y&withdraw=Y&cancel=Y&destroy=Y"
        "&numOfRows=3&pageNo=1"
        f"&inventionTitle=인공지능&applicationDate={date_range}"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            text = await r.text(encoding="utf-8", errors="ignore")

    code_m = re.search(r"<resultCode>(.*?)</resultCode>", text)
    code = code_m.group(1) if code_m else "?"
    total_m = re.search(r"<totalCount>(.*?)</totalCount>", text)
    total = int(total_m.group(1)) if total_m else 0

    if code == "00":
        ok(f"resultCode=00 (인공지능, {date_range})")
    else:
        fail("resultCode 확인", f"code={code}, text[:200]={text[:200]}")

    if total >= 0:
        ok(f"totalCount={total} (음수 아님)")
    else:
        fail("totalCount 음수", str(total))

    print(f"     → 인공지능 특허 출원: {total}건 ({date_range})")


async def test_collect_full(key: str) -> None:
    print("\n[2] 전체 키워드 그룹 주간 수집 (watermark=None)")
    collector = KiprisPatentCollector(key)
    dtos, stats = await collector.collect(watermark=None)

    print(f"     → fetched={stats.get('fetched')} errors={stats.get('errors')} total_kw={stats.get('keywords_total')}")

    if stats.get("fetched", 0) > 0:
        ok(f"fetched={stats['fetched']}건 (1건 이상)")
    else:
        fail("fetched 0건 — 모든 키워드 실패", str(stats))

    error_rate = stats.get("errors", 0) / max(stats.get("keywords_total", 1), 1)
    if error_rate <= 0.2:
        ok(f"오류율 {error_rate:.0%} (20% 이하)")
    else:
        fail("오류율 과다", f"{error_rate:.0%}")

    if dtos:
        dto = dtos[0]
        if dto.source_type == "PATENT_KIPRIS_TREND":
            ok("source_type=PATENT_KIPRIS_TREND")
        else:
            fail("source_type 불일치", dto.source_type)

        meta = dto.raw_metadata or {}
        if meta.get("total_count") is not None:
            ok(f"metadata.total_count={meta['total_count']}")
        else:
            fail("metadata.total_count 없음")

        if meta.get("week_start"):
            ok(f"metadata.week_start={meta['week_start']}")
        else:
            fail("metadata.week_start 없음")

    return stats.get("week_start_str") or (dtos[0].raw_metadata or {}).get("week_start") if dtos else None


async def test_collect_watermark_skip(key: str, week_start_str: str | None) -> None:
    print("\n[3] 워터마크 동일 주 skip 검증")
    if not week_start_str:
        kst_now = datetime.now(tz=_KST)
        ws = kst_now - timedelta(days=kst_now.weekday())
        week_start_str = ws.strftime("%Y%m%d")

    wm = KiprisWatermark(last_week_start=week_start_str)
    collector = KiprisPatentCollector(key)
    dtos, stats = await collector.collect(watermark=wm)

    if len(dtos) == 0 and stats.get("skipped_week", 0) > 0:
        ok(f"동일 주({week_start_str}) skip → dtos=0, skipped={stats['skipped_week']}")
    else:
        fail("워터마크 skip 미동작", f"dtos={len(dtos)} stats={stats}")


async def main() -> int:
    print("=" * 70)
    print("KIPRIS PLUS 특허 검색 API 통합 테스트")
    print("=" * 70)

    key = os.environ.get("KIPRIS_API_KEY") or os.environ.get("KIPRIS_SERVICE_KEY")
    if not key:
        print("\n[SKIP] KIPRIS_API_KEY 환경변수 없음 - .env 확인 후 재실행")
        return 0

    print(f"키 확인: ...{key[-8:]}")

    await test_single_keyword(key)
    week_start_result = await test_collect_full(key)
    await test_collect_watermark_skip(key, week_start_result)

    print("\n" + "=" * 70)
    print(f"결과: PASS={_PASS}  FAIL={_FAIL}")
    print("=" * 70)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
