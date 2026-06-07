"""한국은행 ECOS 통계표/항목 코드 Probe — M2·FDI 등 코드 확정용.

실행: python scripts/bok_ecos_probe.py [검색어]
요구: .env 의 BOK_ECOS_API_KEY, ecos.bok.or.kr 네트워크.

용도:
  1) StatisticTableList 로 통계표 목록을 받아 키워드(통화/직접투자/기준금리)로 필터.
  2) 후보 통계표코드를 bok_ecos_collector._ECOS_TARGETS 에 반영(주석 해제·코드 교체).
"""

import asyncio
import json
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import aiohttp  # noqa: E402

from core.config.settings import get_settings  # noqa: E402

BASE = "https://ecos.bok.or.kr/api"

DEFAULT_KEYWORDS = ("통화", "M2", "직접투자", "기준금리", "국제수지")


async def fetch_table_list(key: str, start: int = 1, end: int = 1000) -> list[dict]:
    url = f"{BASE}/StatisticTableList/{key}/json/kr/{start}/{end}"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as s:
        async with s.get(url) as r:
            data = json.loads(await r.text())
    if "StatisticTableList" in data:
        return data["StatisticTableList"].get("row", [])
    print("RESULT:", data.get("RESULT"))
    return []


async def main() -> None:
    settings = get_settings()
    key = settings.bok_ecos_api_key
    if not key:
        print("[SKIP] BOK_ECOS_API_KEY 미설정. 발급: https://ecos.bok.or.kr/api/#/AuthKeyApply")
        return

    keywords = tuple(sys.argv[1:]) or DEFAULT_KEYWORDS
    print(f"검색 키워드: {keywords}\n")

    rows = await fetch_table_list(key)
    print(f"통계표 총 {len(rows)}건 수신\n")
    for row in rows:
        name = row.get("STAT_NAME", "")
        code = row.get("STAT_CODE", "")
        cycle = row.get("CYCLE", "")
        if any(kw in name for kw in keywords):
            print(f"  {code}  [{cycle}]  {name}")

    print(
        "\n다음 단계: 후보 STAT_CODE 로 "
        "StatisticItemList/{key}/json/kr/1/100/{STAT_CODE} 를 조회해 ITEM_CODE1 을 확정한 뒤,"
        " bok_ecos_collector._ECOS_TARGETS 의 주석을 해제하세요."
    )


if __name__ == "__main__":
    asyncio.run(main())
