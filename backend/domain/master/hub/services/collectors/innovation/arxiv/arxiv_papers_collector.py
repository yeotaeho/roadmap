"""arXiv 분야별 최신 논문을 혁신 선행 신호로 수집한다."""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiohttp

from domain.master.models.transfer.innovation_collect_dto import InnovationCollectDto

logger = logging.getLogger(__name__)

_API_URL = "https://export.arxiv.org/api/query"
_SOURCE_TYPE = "INNOVATION_ARXIV_KR"
_NS = {"atom": "http://www.w3.org/2005/Atom"}
_ARXIV_CATEGORIES: list[tuple[str, str, str]] = [
    ("AI_CS", "cs.AI", "Artificial Intelligence"),
    ("ML_CS", "cs.LG", "Machine Learning"),
    ("BIOINFO", "q-bio.GN", "Genomics"),
    ("BIOMEDICAL", "q-bio.QM", "Quantitative Methods"),
    ("ECONOMICS", "econ.GN", "General Economics"),
    ("FINANCE", "q-fin.GN", "General Finance"),
    ("PHYSICS_APPLY", "physics.app-ph", "Applied Physics"),
    ("ENV_SCI", "physics.ao-ph", "Atmospheric and Oceanic Physics"),
    ("ROBOTICS", "cs.RO", "Robotics"),
    ("SOCIAL_INFO", "cs.SI", "Social and Information Networks"),
    ("ECON_METRICS", "econ.EM", "Econometrics"),  # econ.GN(ECONOMICS)와 중복 방지
]


@dataclass(frozen=True)
class ArxivWatermark:
    last_week_start: str | None = None


def parse_arxiv_feed(xml_text: str, group_name: str, category: str) -> list[InnovationCollectDto]:
    root = ET.fromstring(xml_text)
    rows: list[InnovationCollectDto] = []
    for entry in root.findall("atom:entry", _NS):
        id_text = entry.findtext("atom:id", default="", namespaces=_NS).strip()
        title = " ".join(entry.findtext("atom:title", default="", namespaces=_NS).split())
        if not id_text or not title:
            continue
        arxiv_id = id_text.rsplit("/abs/", 1)[-1]
        summary = " ".join(entry.findtext("atom:summary", default="", namespaces=_NS).split())
        published_raw = entry.findtext("atom:published", default="", namespaces=_NS)
        authors = [
            node.findtext("atom:name", default="", namespaces=_NS).strip()
            for node in entry.findall("atom:author", _NS)
        ]
        authors = [author for author in authors if author]
        try:
            published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
        except ValueError:
            published_at = None
        rows.append(
            InnovationCollectDto(
                source_type=_SOURCE_TYPE,
                source_url=f"https://arxiv.org/abs/{arxiv_id}",
                title=title[:500],
                author_or_assignee=", ".join(authors[:3])[:255] or None,
                abstract_text=summary[:2000] or None,
                raw_metadata={
                    "arxiv_id": arxiv_id,
                    "category": category,
                    "group_name": group_name,
                    "author_count": len(authors),
                    "data_role": "RESEARCH_TREND_SIGNAL",
                },
                published_at=published_at,
            )
        )
    return rows


class ArxivPapersCollector:
    async def collect(
        self,
        *,
        days_back: int = 7,
        max_results: int = 100,
        per_category_cap: int = 300,
        watermark: ArxivWatermark | None = None,
        categories: list[tuple[str, str, str]] | None = None,
        sleep_seconds: float = 1.0,
    ) -> tuple[list[InnovationCollectDto], dict[str, int | str]]:
        now = datetime.now(timezone.utc)
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y%m%d")
        targets = categories or _ARXIV_CATEGORIES
        stats: dict[str, int | str] = {
            "categories_total": len(targets),
            "categories_ok": 0,
            "errors": 0,
            "week_start": week_start,
        }
        if watermark and watermark.last_week_start == week_start:
            stats["skipped_week"] = len(targets)
            return [], stats

        start = now - timedelta(days=max(1, days_back))
        date_range = f"[{start.strftime('%Y%m%d000000')} TO {now.strftime('%Y%m%d235959')}]"
        rows: list[InnovationCollectDto] = []
        timeout = aiohttp.ClientTimeout(total=20)
        headers = {"User-Agent": "RoadmapResearchBot/1.0"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            page_size = max(1, min(max_results, 100))
            for group_name, category, _ in targets:
                # 카테고리당 페이지네이션 — arXiv 는 max_results 만큼 다 안 주므로
                # 실제 반환 수만큼 start 를 전진시키고, 빈 페이지나 상한 도달 시 중단.
                start = 0
                cat_count = 0
                try:
                    while cat_count < per_category_cap:
                        params = {
                            "search_query": f"cat:{category} AND submittedDate:{date_range}",
                            "start": start,
                            "max_results": page_size,
                            "sortBy": "submittedDate",
                            "sortOrder": "descending",
                        }
                        async with session.get(_API_URL, params=params) as response:
                            response.raise_for_status()
                            page = parse_arxiv_feed(await response.text(), group_name, category)
                        if not page:
                            break
                        rows.extend(page)
                        cat_count += len(page)
                        start += len(page)
                        if sleep_seconds > 0:
                            await asyncio.sleep(sleep_seconds)
                    stats["categories_ok"] = int(stats["categories_ok"]) + 1
                except Exception:
                    stats["errors"] = int(stats["errors"]) + 1
                    logger.exception("[arxiv] category=%s 수집 실패", category)
        stats["fetched"] = len(rows)
        return rows, stats


__all__ = ["ArxivPapersCollector", "ArxivWatermark", "parse_arxiv_feed", "_ARXIV_CATEGORIES"]

