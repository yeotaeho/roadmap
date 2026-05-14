"""ALIO 공공기관 사업정보 OpenAPI(15125286) 연결·응답 구조 확인용 Probe.

실행 (backend 디렉터리에서):

  python scripts/alio_probe.py

환경 변수: `ALIO_SERVICE_KEY` 또는 `ALIO_API_KEY` (공공데이터포털 인증키)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import aiohttp
import xmltodict

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from domain.master.hub.services.collectors.economic.alio_public_inst_project_collector import (
    AlioPublicInstProjectCollector,
)


# 공식: `https://apis.data.go.kr/1051000/biz` + `GET /list` (개발계정·명세 기준).
# `B553530/alio/*` 는 다른 서비스로 HTTP 500 등이 날 수 있음.
_URL_CANDIDATES: tuple[str, ...] = (
    AlioPublicInstProjectCollector.BASE_URL,
    "https://apis.data.go.kr/1051000/biz/list",
    "https://apis.data.go.kr/B553530/alio/getProjectInfo",
    "http://apis.data.go.kr/B553530/alio/getProjectInfo",
)


def _ensure_list(value: Any) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first_item_keys(data: dict) -> list[str]:
    """첫 레코드 키: NKOD `result[]` 또는 표준 `response.body.items.item`."""
    r = data.get("result")
    if isinstance(r, list) and r and isinstance(r[0], dict):
        return sorted(r[0].keys())
    resp = data.get("response")
    if not isinstance(resp, dict):
        resp = data
    body = resp.get("body")
    if not isinstance(body, dict):
        return []
    items = body.get("items")
    if isinstance(items, dict):
        raw = _ensure_list(items.get("item"))
    else:
        raw = _ensure_list(body.get("item"))
    if not raw or not isinstance(raw[0], dict):
        return []
    return sorted(raw[0].keys())


async def _try_url(
    session: aiohttp.ClientSession,
    url: str,
    service_key: str,
) -> tuple[int, str, dict | None]:
    params = {
        "serviceKey": service_key,
        "pageNo": "1",
        "numOfRows": "5",
        "resultType": "json",
    }
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=45)) as resp:
            text = await resp.text()
            return resp.status, text, None
    except aiohttp.ClientError as e:
        return -1, str(e), None


async def main() -> None:
    from core.config.settings import get_settings

    print("=" * 72)
    print("ALIO 공공기관 사업정보 API Probe (data.go.kr 15125286 → raw_economic_data)")
    print("=" * 72)

    settings = get_settings()
    key = (settings.alio_service_key or "").strip()
    if not key:
        print("\n[오류] ALIO_SERVICE_KEY / ALIO_API_KEY 가 설정되어 있지 않습니다.")
        print("        프로젝트 루트 `.env` 에 키를 추가한 뒤 다시 실행하세요.")
        return

    async with aiohttp.ClientSession() as session:
        for url in _URL_CANDIDATES:
            print(f"\n--- 요청 URL: {url} ---")
            status, body_text, _ = await _try_url(session, url, key)
            print(f"HTTP 상태 코드: {status}")
            preview = (body_text or "")[:2000]
            print(f"응답 본문 앞 2000자:\n{preview}")
            if status != 200:
                print("[안내] 다음 후보 URL을 시도합니다.\n")
                continue

            stripped = body_text.strip()
            parsed: dict | None = None
            if stripped.startswith("{"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    print("[경고] JSON 파싱 실패")
            else:
                try:
                    parsed = xmltodict.parse(stripped)
                except Exception as e:
                    print(f"[경고] XML 파싱 실패: {e}")

            if isinstance(parsed, dict):
                print("\n[파싱 결과] 최상위 키:", list(parsed.keys())[:30])
                keys = _first_item_keys(parsed)
                if keys:
                    print(f"[첫 item] 필드명 ({len(keys)}개): {keys}")
                else:
                    print("[첫 item] item 을 찾지 못했습니다. 원본 구조를 확인하세요.")

            if status == 200 and stripped:
                print("\n[결론] 위 URL로 정상 응답이 왔습니다. `AlioPublicInstProjectCollector.BASE_URL` 과 비교하세요.")
                break
        else:
            print("\n[결론] 모든 후보 URL이 실패했습니다. data.go.kr 포털에서 실제 엔드포인트를 확인하세요.")


if __name__ == "__main__":
    asyncio.run(main())
