# PyPI 패키지 다운로드 통계 수집 (기술 채택 선행지표)

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp

from domain.master.models.transfer.tech_adoption_collect_dto import TechAdoptionCollectDto

logger = logging.getLogger(__name__)

_BASE_URL = "https://pypistats.org/api/packages/{pkg}/recent"

_SECTOR_PACKAGES: dict[str, list[str]] = {
    "AI_ML": [
        "torch", "tensorflow", "transformers", "langchain", "openai",
        "scikit-learn", "keras", "xgboost", "lightgbm", "anthropic",
        "huggingface-hub", "diffusers", "sentence-transformers",
        "llama-index", "crewai",
    ],
    "DATA": [
        "pandas", "numpy", "polars", "dask", "pyspark",
        "sqlalchemy", "dbt-core", "great-expectations", "apache-airflow",
    ],
    "WEB": [
        "fastapi", "django", "flask", "streamlit", "gradio",
        "celery", "uvicorn", "pydantic",
    ],
    "DEVOPS": [
        "docker", "kubernetes", "ansible", "python-terraform",
        "boto3", "google-cloud-storage",
    ],
}


def _this_monday() -> date:
    today = datetime.now().date()
    return today - timedelta(days=today.weekday())


class PypiDownloadsCollector:
    """PyPI 패키지 주간 다운로드 통계를 수집한다."""

    async def collect(self) -> tuple[list[TechAdoptionCollectDto], dict[str, int | str]]:
        monday = _this_monday()

        rows: list[TechAdoptionCollectDto] = []
        attempted = 0
        failed = 0

        sem = asyncio.Semaphore(1)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for sector, packages in _SECTOR_PACKAGES.items():
                for pkg in packages:
                    attempted += 1
                    dto = await self._fetch_package(session, sem, pkg, sector, monday)
                    if dto is None:
                        failed += 1
                    else:
                        rows.append(dto)

        stats: dict[str, int | str] = {
            "packages_attempted": attempted,
            "packages_collected": attempted - failed,
            "packages_failed": failed,
            "week_start": str(monday),
        }
        return rows, stats

    async def _fetch_package(
        self,
        session: aiohttp.ClientSession,
        sem: asyncio.Semaphore,
        pkg: str,
        sector: str,
        monday: date,
    ) -> TechAdoptionCollectDto | None:
        url = _BASE_URL.format(pkg=pkg)
        retries = 3
        backoff = 1.0

        async with sem:
            for attempt in range(retries):
                try:
                    async with session.get(url) as resp:
                        if resp.status == 429:
                            if attempt < retries - 1:
                                logger.warning("PyPI 429 for %s, retry in %.1fs", pkg, backoff)
                                await asyncio.sleep(backoff)
                                backoff *= 2
                                continue
                            logger.error("PyPI 429 for %s after %d retries", pkg, retries)
                            return None
                        if resp.status != 200:
                            logger.warning("PyPI %s returned HTTP %d", pkg, resp.status)
                            return None
                        data = await resp.json()
                except Exception:
                    logger.exception("PyPI 요청 실패: %s", pkg)
                    return None
                finally:
                    await asyncio.sleep(0.5)

                stats_data: dict[str, Any] = data.get("data", {})
                last_week: int = stats_data.get("last_week", 0)

                return TechAdoptionCollectDto(
                    ecosystem="pypi",
                    package_name=pkg,
                    sector=sector,
                    weekly_downloads=last_week,
                    week_start_date=monday,
                    raw_metadata={
                        "last_day": stats_data.get("last_day", 0),
                        "last_week": last_week,
                        "last_month": stats_data.get("last_month", 0),
                    },
                )

        return None
