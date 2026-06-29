# npm 패키지 다운로드 통계 수집 (기술 채택 선행지표)

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import aiohttp

from domain.master.models.transfer.tech_adoption_collect_dto import TechAdoptionCollectDto

logger = logging.getLogger(__name__)

_SECTOR_PACKAGES: dict[str, list[str]] = {
    "FRONTEND": [
        "react", "vue", "svelte", "@angular/core", "next",
        "nuxt", "astro", "solid-js", "htmx.org",
    ],
    "AI_ML": [
        "@langchain/core", "openai", "@anthropic-ai/sdk",
        "llamaindex", "ai", "@huggingface/inference",
    ],
    "RUNTIME": [
        "typescript", "bun", "esbuild", "vite", "turbo",
        "webpack", "rollup",
    ],
    "MOBILE": [
        "react-native", "expo", "@capacitor/core", "ionic",
    ],
    "STYLING": [
        "tailwindcss", "sass", "styled-components",
        "@emotion/react", "postcss",
    ],
}


def _this_monday() -> date:
    today = datetime.now().date()
    return today - timedelta(days=today.weekday())


class NpmDownloadsCollector:
    """npm 패키지 주간 다운로드 통계를 일괄 수집한다."""

    async def collect(self) -> tuple[list[TechAdoptionCollectDto], dict[str, int | str]]:
        monday = _this_monday()

        pkg_to_sector: dict[str, str] = {}
        all_packages: list[str] = []
        for sector, packages in _SECTOR_PACKAGES.items():
            for pkg in packages:
                if pkg not in pkg_to_sector:
                    pkg_to_sector[pkg] = sector
                    all_packages.append(pkg)

        rows: list[TechAdoptionCollectDto] = []
        failed = 0
        timeout = aiohttp.ClientTimeout(total=30)

        # scoped 패키지(@로 시작)는 벌크 API에서 /가 path로 해석되어 HTTP 400 → 개별 요청
        unscoped = [p for p in all_packages if not p.startswith("@")]
        scoped = [p for p in all_packages if p.startswith("@")]
        bulk_data: dict = {}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            if unscoped:
                bulk_url = "https://api.npmjs.org/downloads/range/last-week/" + ",".join(unscoped)
                try:
                    async with session.get(bulk_url) as resp:
                        if resp.status == 200:
                            bulk_data = await resp.json()
                        else:
                            logger.error("npm 벌크 API HTTP %d", resp.status)
                except Exception:
                    logger.exception("npm 벌크 요청 실패")

            for pkg in scoped:
                try:
                    url = f"https://api.npmjs.org/downloads/range/last-week/{pkg}"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            bulk_data[pkg] = data
                        else:
                            logger.warning("npm scoped %s HTTP %d", pkg, resp.status)
                except Exception:
                    logger.warning("npm scoped %s 요청 실패", pkg)

        for pkg in all_packages:
            pkg_data = bulk_data.get(pkg)
            if pkg_data is None:
                logger.warning("npm 응답에 패키지 없음: %s", pkg)
                failed += 1
                continue

            downloads_list: list[dict] = pkg_data.get("downloads", [])
            total_week: int = sum(d.get("downloads", 0) for d in downloads_list)
            daily_summary = [{"day": d["day"], "downloads": d["downloads"]} for d in downloads_list]

            rows.append(
                TechAdoptionCollectDto(
                    ecosystem="npm",
                    package_name=pkg,
                    sector=pkg_to_sector.get(pkg, "UNKNOWN"),
                    weekly_downloads=total_week,
                    week_start_date=monday,
                    raw_metadata={"daily_downloads": daily_summary},
                )
            )

        stats: dict[str, int | str] = {
            "packages_attempted": len(all_packages),
            "packages_collected": len(rows),
            "packages_failed": failed,
            "week_start": str(monday),
        }
        return rows, stats
