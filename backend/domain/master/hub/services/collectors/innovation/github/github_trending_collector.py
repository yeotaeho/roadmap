"""GitHub Search API로 분야별 신규·모멘텀 저장소를 수집한다."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from domain.master.models.transfer.innovation_collect_dto import InnovationCollectDto

logger = logging.getLogger(__name__)

_API_URL = "https://api.github.com/search/repositories"
_SOURCE_TYPE = "INNOVATION_GITHUB_TRENDING"
_GITHUB_TOPIC_GROUPS: list[tuple[str, list[str]]] = [
    ("AI_ML",        ["machine-learning", "deep-learning", "llm", "generative-ai"]),
    ("BIOINFO",      ["bioinformatics", "genomics", "drug-discovery"]),
    ("FINTECH",      ["fintech", "defi", "blockchain"]),
    ("EDUTECH",      ["education", "e-learning", "edtech"]),
    ("CLIMATE",      ["climate-change", "carbon-neutral", "renewable-energy"]),
    ("HEALTHTECH",   ["healthcare", "medical-imaging", "digital-health"]),
    ("FOODTECH",     ["food-tech", "agriculture", "precision-farming"]),
    ("CREATOR_TOOL", ["creative-tools", "design", "content-creation"]),
    ("ROBOTICS",     ["robotics", "autonomous-vehicles", "drone"]),
    ("SOCIAL_GOOD",  ["social-impact", "nonprofit", "civic-tech"]),
]

# signal_mode 상수
_MODE_NEW = "new"         # 이번 주 신규 생성 레포 (growth signal)
_MODE_MOMENTUM = "momentum"  # 이번 주 활발히 push된 기존 인기 레포 (momentum signal)


@dataclass(frozen=True)
class GithubWatermark:
    last_week_start: str | None = None


def github_item_to_dto(
    item: dict[str, Any],
    group_name: str,
    week_start: str,
    signal_mode: str = _MODE_NEW,
) -> InnovationCollectDto | None:
    full_name = str(item.get("full_name") or "").strip()
    html_url = str(item.get("html_url") or "").strip()
    if not full_name or not html_url:
        return None
    owner = str((item.get("owner") or {}).get("login") or full_name.split("/", 1)[0])
    created_raw = str(item.get("created_at") or "")
    try:
        published_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
    except ValueError:
        published_at = None
    stars = int(item.get("stargazers_count") or 0)

    # signal_mode별 source_url 분리 → UNIQUE 충돌 없이 두 신호 공존
    source_url = (
        f"{html_url}?week={week_start}"
        if signal_mode == _MODE_NEW
        else f"{html_url}?week={week_start}&mode=momentum"
    )
    data_role = (
        "OPENSOURCE_GROWTH_SIGNAL"    # 신규 레포: 초기 성장 신호
        if signal_mode == _MODE_NEW
        else "OPENSOURCE_MOMENTUM_SIGNAL"  # 기존 레포: 지속 모멘텀 신호
    )
    mode_label = "new" if signal_mode == _MODE_NEW else "⚡"
    return InnovationCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=source_url,
        title=f"[{group_name}][{mode_label}] {full_name} stars={stars} ({week_start}W)"[:500],
        author_or_assignee=owner[:255] or None,
        abstract_text=str(item.get("description") or "")[:2000] or None,
        raw_metadata={
            "full_name": full_name,
            "stars": stars,
            "forks": int(item.get("forks_count") or 0),
            "language": item.get("language"),
            "topics": item.get("topics") or [],
            "group_name": group_name,
            "week_start": week_start,
            "signal_mode": signal_mode,
            "data_role": data_role,
        },
        published_at=published_at,
    )


class GithubTrendingCollector:
    def __init__(self, token: str | None = None) -> None:
        self._token = token.strip() if token else None

    async def collect(
        self,
        *,
        days_back: int = 7,
        watermark: GithubWatermark | None = None,
        topic_groups: list[tuple[str, list[str]]] | None = None,
        per_page: int = 30,
        sleep_seconds: float | None = None,
        include_momentum: bool = True,
        momentum_min_stars: int = 1000,
    ) -> tuple[list[InnovationCollectDto], dict[str, int | str]]:
        """분야별 GitHub 저장소를 수집한다.

        include_momentum=True(기본)이면 신규 레포(growth)와 함께
        이번 주 커밋 활동이 있는 기존 인기 레포(momentum)도 수집한다.
        """
        now = datetime.now(timezone.utc)
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        watermark_key = week_start.replace("-", "")
        targets = topic_groups or _GITHUB_TOPIC_GROUPS
        topic_count = sum(len(topics) for _, topics in targets)
        # 모멘텀 패스 포함 시 총 요청 수 2배
        total_requests = topic_count * (2 if include_momentum else 1)
        stats: dict[str, int | str] = {
            "topics_total": topic_count,
            "topics_ok": 0,
            "errors": 0,
            "week_start": watermark_key,
            "momentum_included": include_momentum,
        }
        if watermark and watermark.last_week_start == watermark_key:
            stats["skipped_week"] = topic_count
            return [], stats

        created_from = (now - timedelta(days=max(1, days_back))).date().isoformat()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "roadmap-pipeline",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request_interval = sleep_seconds
        if request_interval is None:
            request_interval = 2.1 if self._token else 6.1

        rows_by_url: dict[str, InnovationCollectDto] = {}
        timeout = aiohttp.ClientTimeout(total=20)
        request_no = 0

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            # ── Pass 1: 신규 레포 (created this week, stars > 50) ──────────────
            for group_name, topics in targets:
                for topic in topics:
                    request_no += 1
                    params = {
                        "q": f"topic:{topic} created:>={created_from} stars:>50",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": max(1, min(per_page, 100)),
                    }
                    await self._fetch_and_store(
                        session, params, group_name, watermark_key,
                        _MODE_NEW, rows_by_url, stats,
                    )
                    if request_no < total_requests and request_interval > 0:
                        await asyncio.sleep(request_interval)

            # ── Pass 2: 모멘텀 레포 (pushed this week, stars > 1000) ──────────
            if include_momentum:
                for group_name, topics in targets:
                    for topic in topics:
                        request_no += 1
                        params = {
                            "q": f"topic:{topic} pushed:>={week_start} stars:>{momentum_min_stars}",
                            "sort": "stars",
                            "order": "desc",
                            "per_page": max(1, min(per_page, 100)),
                        }
                        await self._fetch_and_store(
                            session, params, group_name, watermark_key,
                            _MODE_MOMENTUM, rows_by_url, stats,
                        )
                        if request_no < total_requests and request_interval > 0:
                            await asyncio.sleep(request_interval)

        rows = list(rows_by_url.values())
        stats["fetched"] = len(rows)
        return rows, stats

    async def _fetch_and_store(
        self,
        session: aiohttp.ClientSession,
        params: dict[str, Any],
        group_name: str,
        week_start: str,
        signal_mode: str,
        rows_by_url: dict[str, InnovationCollectDto],
        stats: dict[str, int | str],
    ) -> None:
        topic = str(params.get("q", "")).split()[0]  # 로그용
        try:
            async with session.get(_API_URL, params=params) as response:
                if response.status in {403, 429}:
                    remaining = response.headers.get("X-RateLimit-Remaining")
                    raise RuntimeError(
                        f"GitHub rate limit status={response.status} remaining={remaining}"
                    )
                response.raise_for_status()
                data = await response.json()
            for item in data.get("items") or []:
                dto = github_item_to_dto(item, group_name, week_start, signal_mode)
                if dto and dto.source_url:
                    rows_by_url.setdefault(dto.source_url, dto)
            stats["topics_ok"] = int(stats["topics_ok"]) + 1
        except Exception:
            stats["errors"] = int(stats["errors"]) + 1
            logger.exception("[github][%s] topic=%s 수집 실패", signal_mode, topic)


__all__ = [
    "GithubTrendingCollector",
    "GithubWatermark",
    "github_item_to_dto",
    "_GITHUB_TOPIC_GROUPS",
    "_MODE_NEW",
    "_MODE_MOMENTUM",
]
