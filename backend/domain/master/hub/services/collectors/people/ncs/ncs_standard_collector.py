# NCS 국가직무능력표준 기준정보 OpenAPI (data.go.kr 15128213) 기반 역량 온톨로지 수집

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import aiohttp

from domain.master.models.transfer.ncs_master_dto import NcsMasterDto

logger = logging.getLogger(__name__)

_BASE_URL = "https://apis.data.go.kr/B490007/hrdkapi"

# 오퍼레이션명 → (레벨, 입력 파라미터 키 목록, 출력 코드 키, 출력 이름 키)
_OPS = {
    1: ("NCS001", [],                                                          "NCS_LCLAS_CD", "NCS_LCLAS_CDNM"),
    2: ("NCS002", ["NCS_LCLAS_CD"],                                            "NCS_MCLAS_CD", "NCS_MCLAS_CDNM"),
    3: ("NCS003", ["NCS_LCLAS_CD", "NCS_MCLAS_CD"],                            "NCS_SCLAS_CD", "NCS_SCLAS_CDNM"),
    4: ("NCS004", ["NCS_LCLAS_CD", "NCS_MCLAS_CD", "NCS_SCLAS_CD"],            "NCS_SUBD_CD",  "NCS_SUBD_CDNM"),
    5: ("NCS005", ["NCS_LCLAS_CD", "NCS_MCLAS_CD", "NCS_SCLAS_CD", "NCS_SUBD_CD"], "NCS_CL_CD", "COMPE_UNIT_NAME"),
    6: ("NCS006", ["NCS_CL_CD"],                                               "COMPE_UNIT_FACTR_NO_CD", "COMPE_UNIT_FACTR_NAME"),
}

_LEVEL_SOURCE_TYPES = {
    1: "NCS_CLASSIFICATION",
    2: "NCS_CLASSIFICATION",
    3: "NCS_CLASSIFICATION",
    4: "NCS_CLASSIFICATION",
    5: "NCS_COMPETENCY_UNIT",
    6: "NCS_COMPETENCY_ELEMENT",
}


def _extract_items(data: dict) -> list[dict]:
    """data.go.kr 표준 응답 → item 리스트."""
    raw = data.get("response", {}).get("body", {}).get("items") or {}
    if isinstance(raw, list):
        return raw
    items = raw.get("item", [])
    if isinstance(items, dict):
        return [items]
    return items or []


def _dedup_latest(items: list[dict], code_key: str) -> list[dict]:
    """동일 코드의 여러 버전 중 NCS_DEGR 최대값(최신) 하나만 유지."""
    seen: dict[str, dict] = {}
    for it in items:
        cd = it.get(code_key)
        if cd is None:
            continue
        if cd not in seen or (it.get("NCS_DEGR", 0) > seen[cd].get("NCS_DEGR", 0)):
            seen[cd] = it
    return list(seen.values())


class NcsStandardCollector:
    """NCS 국가직무능력표준 기준정보 API (data.go.kr 15128213) 역량 온톨로지 수집기.

    BFS로 L1→L6 계층을 순회하며 NcsMasterDto 리스트를 반환한다.
    max_depth로 탐색 레벨을 제한할 수 있다 (기본 5 = 능력단위까지, 6 = 요소까지).
    """

    BASE_URL = _BASE_URL

    def __init__(self, service_key: str) -> None:
        if not service_key or not service_key.strip():
            raise ValueError("NCS Standard API 키가 비어 있습니다. NCS_STANDARD_SERVICE_KEY를 설정하세요.")
        self._service_key = service_key.strip()

    async def _fetch_level(
        self,
        session: aiohttp.ClientSession,
        level: int,
        parent_codes: dict[str, str],
        sem: asyncio.Semaphore,
    ) -> list[dict]:
        """단일 레벨 API 호출 → deduped item 리스트."""
        op_name, param_keys, code_key, _ = _OPS[level]
        url = f"{self.BASE_URL}/{op_name}"
        params: dict[str, str] = {
            "serviceKey": self._service_key,
            "returnType": "json",
            "numOfRows": "1000",
            "pageNo": "1",
        }
        for pk in param_keys:
            if pk in parent_codes:
                params[pk] = parent_codes[pk]

        async with sem:
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.warning("NCS API HTTP %d — L%d params=%s", resp.status, level, parent_codes)
                        return []
                    data = await resp.json(content_type=None)
            except Exception as exc:
                logger.warning("NCS API 오류 — L%d: %s", level, exc)
                return []
            finally:
                await asyncio.sleep(0.3)

        rc = data.get("response", {}).get("header", {}).get("resultCode", "")
        if rc != "00":
            msg = data.get("response", {}).get("header", {}).get("resultMsg", "")
            logger.debug("NCS API 비정상 코드 L%d rc=%s msg=%s params=%s", level, rc, msg, parent_codes)
            return []

        items = _extract_items(data)
        return _dedup_latest(items, code_key)

    async def collect(
        self, *, max_depth: int = 5
    ) -> tuple[list[NcsMasterDto], dict[str, int]]:
        """NCS 계층 BFS 수집.

        Returns:
            (dtos, stats) — dtos: NcsMasterDto 리스트,
                            stats: {"l1": n, "l2": n, ...}
        """
        max_depth = max(1, min(max_depth, 6))
        sem = asyncio.Semaphore(3)
        timeout = aiohttp.ClientTimeout(total=30)
        collected: list[NcsMasterDto] = []
        stats: dict[str, int] = {f"l{i}": 0 for i in range(1, max_depth + 1)}
        now = datetime.now(timezone.utc)

        # BFS 큐: (level, item, parent_codes_dict, ancestors_dict)
        # ancestors: {l1: (cd, nm), l2: ..., ...} — 탈정규화용
        queue: list[tuple[int, dict, dict[str, str], dict[int, tuple[str, str]]]] = []

        async with aiohttp.ClientSession(timeout=timeout) as session:
            # L1 루트
            l1_items = await self._fetch_level(session, 1, {}, sem)
            logger.info("NCS L1 대분류: %d건", len(l1_items))
            for it in l1_items:
                queue.append((1, it, {}, {}))

            for level, item, parent_codes, ancestors in queue:
                _, _, code_key, name_key = _OPS[level]
                code = item.get(code_key)
                name = item.get(name_key)
                if not code or not name:
                    continue

                # 조상 dict 갱신 (L1~L4만 탈정규화, L5/L6는 NCS_CL_CD 기반)
                new_ancestors = dict(ancestors)
                if level <= 4:
                    new_ancestors[level] = (str(code), str(name))

                # 현재 레벨 parent_codes 업데이트
                new_parent_codes = dict(parent_codes)
                if level == 1:
                    new_parent_codes["NCS_LCLAS_CD"] = str(code)
                elif level == 2:
                    new_parent_codes["NCS_MCLAS_CD"] = str(code)
                elif level == 3:
                    new_parent_codes["NCS_SCLAS_CD"] = str(code)
                elif level == 4:
                    new_parent_codes["NCS_SUBD_CD"] = str(code)
                elif level == 5:
                    new_parent_codes["NCS_CL_CD"] = str(code)

                def _anc(lv: int) -> tuple[str | None, str | None]:
                    t = new_ancestors.get(lv)
                    return (t[0], t[1]) if t else (None, None)

                # L4에서 추가 메타 (직무정의, duty_def)
                description = None
                performance_criteria = None
                knowledge_skills = None
                if level == 4:
                    description = item.get("DUTY_DEF")
                elif level == 5:
                    description = item.get("COMPE_UNIT_DEF")
                    level_val = item.get("COMPE_UNIT_LEVEL")
                    knowledge_skills = {"level": level_val} if level_val else None
                elif level == 6:
                    performance_criteria = item.get("COMPE_UNIT_FACTR_NAME")
                    knowledge_skills = {
                        "factr_no": item.get("COMPE_UNIT_FACTR_NO"),
                        "level": item.get("COMPE_UNIT_FACTR_LEVEL"),
                    }

                # ncs_code: L1~L4는 short code, L5는 NCS_CL_CD, L6는 요소코드
                ncs_code = str(code)

                dto = NcsMasterDto(
                    source_type=_LEVEL_SOURCE_TYPES[level],
                    ncs_code=ncs_code[:30],
                    level=level,
                    name=str(name)[:300],
                    parent_code=str(list(parent_codes.values())[-1]) if parent_codes else None,
                    category_l1_code=_anc(1)[0],
                    category_l1_name=_anc(1)[1],
                    category_l2_code=_anc(2)[0],
                    category_l2_name=_anc(2)[1],
                    category_l3_code=_anc(3)[0],
                    category_l3_name=_anc(3)[1],
                    category_l4_code=_anc(4)[0],
                    category_l4_name=_anc(4)[1],
                    description=description,
                    performance_criteria=performance_criteria,
                    knowledge_skills=knowledge_skills,
                    raw_metadata={k: v for k, v in item.items()},
                    collected_at=now,
                )
                collected.append(dto)
                stats[f"l{level}"] += 1

                # 자식 레벨 예약
                if level < max_depth:
                    child_level = level + 1
                    child_items = await self._fetch_level(
                        session, child_level, new_parent_codes, sem
                    )
                    for child_item in child_items:
                        queue.append((child_level, child_item, new_parent_codes, new_ancestors))

        logger.info(
            "NCS Standard 수집 완료: 총 %d건 — %s",
            len(collected),
            {k: v for k, v in stats.items() if v > 0},
        )
        return collected, stats


__all__ = ["NcsStandardCollector"]
