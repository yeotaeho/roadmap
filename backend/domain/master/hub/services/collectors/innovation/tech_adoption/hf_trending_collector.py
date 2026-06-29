# HuggingFace Hub 트렌딩 모델 수집 (AI 기술 채택 선행지표)

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp

from domain.master.models.transfer.innovation_collect_dto import InnovationCollectDto

logger = logging.getLogger(__name__)

_SOURCE_TYPE = "INNOVATION_HF_TRENDING"
_HF_API_BASE = "https://huggingface.co/api/models"

_HF_TAGS: list[str] = [
    "text-generation", "text-to-image", "automatic-speech-recognition",
    "text-classification", "token-classification", "feature-extraction",
    "translation", "summarization", "question-answering", "object-detection",
]


def _this_monday() -> datetime:
    today = datetime.now()
    return today - timedelta(days=today.weekday())


class HfTrendingCollector:
    """HuggingFace Hub 태그별 상위 다운로드 모델을 수집한다."""

    async def collect(self, *, top_n: int = 30) -> tuple[list[InnovationCollectDto], dict[str, int | str]]:
        monday = _this_monday().replace(hour=0, minute=0, second=0, microsecond=0)
        monday_str = monday.strftime("%Y-%m-%d")

        rows: list[InnovationCollectDto] = []
        seen_model_ids: set[str] = set()
        failed_tags = 0

        sem = asyncio.Semaphore(2)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for tag in _HF_TAGS:
                tag_rows = await self._fetch_tag(
                    session, sem, tag, top_n, monday, monday_str, seen_model_ids
                )
                if tag_rows is None:
                    failed_tags += 1
                else:
                    rows.extend(tag_rows)

        stats: dict[str, int | str] = {
            "tags_attempted": len(_HF_TAGS),
            "tags_failed": failed_tags,
            "models_collected": len(rows),
            "week_start": monday_str,
        }
        return rows, stats

    async def _fetch_tag(
        self,
        session: aiohttp.ClientSession,
        sem: asyncio.Semaphore,
        tag: str,
        top_n: int,
        monday: datetime,
        monday_str: str,
        seen_model_ids: set[str],
    ) -> list[InnovationCollectDto] | None:
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

        tag_rows: list[InnovationCollectDto] = []
        for model in models:
            model_id: str = model.get("id", "")
            if not model_id or model_id in seen_model_ids:
                continue
            seen_model_ids.add(model_id)

            downloads: int = model.get("downloads", 0)
            likes: int = model.get("likes", 0)
            tags: list[str] = model.get("tags", [])
            pipeline_tag: str = model.get("pipeline_tag", tag)

            # org/model → org 추출
            author = model_id.split("/")[0] if "/" in model_id else model_id

            tag_rows.append(
                InnovationCollectDto(
                    source_type=_SOURCE_TYPE,
                    source_url=f"https://huggingface.co/{model_id}?week={monday_str}",
                    title=f"HF {model_id} ({tag}): {downloads:,} downloads, {likes:,} likes",
                    author_or_assignee=author,
                    abstract_text=", ".join(tags),
                    raw_metadata={
                        "pipeline_tag": pipeline_tag,
                        "model_id": model_id,
                        "downloads": downloads,
                        "likes": likes,
                        "tags": tags,
                    },
                    published_at=monday,
                )
            )

        return tag_rows
