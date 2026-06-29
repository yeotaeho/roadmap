# HuggingFace Hub 트렌딩 모델 수집 (AI 기술 채택 선행지표)

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

import aiohttp

from domain.master.models.transfer.tech_adoption_collect_dto import TechAdoptionCollectDto

logger = logging.getLogger(__name__)

_HF_API_BASE = "https://huggingface.co/api/models"

_HF_TAGS: list[str] = [
    "text-generation", "text-to-image", "automatic-speech-recognition",
    "text-classification", "token-classification", "feature-extraction",
    "translation", "summarization", "question-answering", "object-detection",
]

# HF pipeline_tag → sector 매핑
_TAG_TO_SECTOR: dict[str, str] = {
    "text-generation": "AI_ML",
    "text-to-image": "AI_ML",
    "automatic-speech-recognition": "AI_ML",
    "text-classification": "AI_ML",
    "token-classification": "AI_ML",
    "feature-extraction": "AI_ML",
    "translation": "AI_ML",
    "summarization": "AI_ML",
    "question-answering": "AI_ML",
    "object-detection": "AI_ML",
}


def _this_monday() -> date:
    today = datetime.now().date()
    return today - timedelta(days=today.weekday())


class HfTrendingCollector:
    """HuggingFace Hub 태그별 상위 다운로드 모델을 수집한다."""

    async def collect(self, *, top_n: int = 30) -> tuple[list[TechAdoptionCollectDto], dict[str, int | str]]:
        monday = _this_monday()

        rows: list[TechAdoptionCollectDto] = []
        seen_model_ids: set[str] = set()
        failed_tags = 0

        sem = asyncio.Semaphore(2)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for tag in _HF_TAGS:
                tag_rows = await self._fetch_tag(
                    session, sem, tag, top_n, monday, seen_model_ids
                )
                if tag_rows is None:
                    failed_tags += 1
                else:
                    rows.extend(tag_rows)

        stats: dict[str, int | str] = {
            "tags_attempted": len(_HF_TAGS),
            "tags_failed": failed_tags,
            "models_collected": len(rows),
            "week_start": str(monday),
        }
        return rows, stats

    async def _fetch_tag(
        self,
        session: aiohttp.ClientSession,
        sem: asyncio.Semaphore,
        tag: str,
        top_n: int,
        monday: date,
        seen_model_ids: set[str],
    ) -> list[TechAdoptionCollectDto] | None:
        url = f"{_HF_API_BASE}?sort=downloads&direction=-1&limit={top_n}&filter={tag}"
        async with sem:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning("HF API %s HTTP %d", tag, resp.status)
                        return None
                    models: list[dict] = await resp.json()
            except Exception:
                logger.exception("HF API 요청 실패: %s", tag)
                return None
            finally:
                await asyncio.sleep(0.3)

        tag_rows: list[TechAdoptionCollectDto] = []
        for rank, model in enumerate(models, start=1):
            model_id: str = model.get("id", "")
            if not model_id or model_id in seen_model_ids:
                continue
            seen_model_ids.add(model_id)

            downloads: int = model.get("downloads", 0)
            likes: int = model.get("likes", 0)
            pipeline_tag: str = model.get("pipeline_tag", tag)

            tag_rows.append(
                TechAdoptionCollectDto(
                    ecosystem="hf",
                    package_name=model_id,
                    sector=_TAG_TO_SECTOR.get(tag, "AI_ML"),
                    weekly_downloads=None,  # HF API는 주간 단위 다운로드 미제공
                    week_start_date=monday,
                    raw_metadata={
                        "downloads_alltime": downloads,
                        "likes": likes,
                        "pipeline_tag": pipeline_tag,
                        "trending_rank": rank,
                        "tags": model.get("tags", []),
                    },
                )
            )

        return tag_rows
