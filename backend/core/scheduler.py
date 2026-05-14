"""Bronze 자동 수집 스케줄러.

APScheduler ``AsyncIOScheduler`` 를 FastAPI 이벤트 루프 위에 띄워, ``BronzeEconomicIngestService``·
``BronzeOpportunityIngestService`` 의 ingest 메서드를 정해진 주기로 실행한다.

설계 원칙
=========

1. **독립 세션**: 각 job 은 ``AsyncSessionLocal()`` 로 자기 자신의 ``AsyncSession`` 을 새로 만든다.
   - 잡 간 트랜잭션 격리 + 한 잡이 길어도 다른 잡에 영향 X.
2. **격리된 실패**: 각 job 의 본문은 ``try/except`` 로 감싸 예외를 로깅만 한다.
   - APScheduler 입장에서 잡이 성공 처리되어 다음 트리거가 정상 동작.
3. **단일 인스턴스 보장**: ``max_instances=1`` + ``coalesce=True``.
   - 시계 변경/지연으로 중복 트리거가 누적되어도 한 번만 실행.
4. **누락 보상**: ``misfire_grace_time=3600`` (1 시간).
   - 서버 재시작 직후에도 1 시간 내라면 누락된 잡을 실행.
5. **외부 ON/OFF**: ``settings.scheduler_enabled`` 가 False 면 ``start_scheduler()`` 가 no-op.

수집 그룹
========

- **일일** (오전 9 시 KST):
  DART · MSIT 보도자료/사업공고/R&D 예산 · Wowtale · Platum · StartupRecipe · SMES Opportunity
- **주간** (월요일 오전 9 시 KST):
  ALIO 공공기관 사업정보 · Yahoo Finance ETF · Yahoo Macro

ALIO/Yahoo 는 데이터 자체가 일 단위로 빈번하게 변하지 않거나 API 쿼터 비용이 비싸므로 주간으로 분리.
MOEF 로컬 PDF 는 **사용자 업로드** 시나리오라 스케줄링하지 않는다.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config.settings import get_settings
from core.database import AsyncSessionLocal
from domain.master.hub.services.bronze_economic_ingest_service import (
    BronzeEconomicIngestService,
)
from domain.master.hub.services.bronze_opportunity_ingest_service import (
    BronzeOpportunityIngestService,
)

logger = logging.getLogger(__name__)


_scheduler: AsyncIOScheduler | None = None


# ---------------------------------------------------------------------------
# job runner — 공통 격리 컨테이너
# ---------------------------------------------------------------------------


async def _run_job(
    job_name: str,
    coro_factory: Callable[[], Awaitable[Any]],
) -> None:
    """이름 + 본문 실행. 예외는 로깅만 하고 swallow.

    APScheduler 입장에서 잡이 정상 종료된 것으로 간주되어, 다음 트리거가 보장됨.
    """
    logger.info("[scheduler] job start: %s", job_name)
    try:
        result = await coro_factory()
        logger.info("[scheduler] job done : %s result=%s", job_name, result)
    except Exception:
        logger.exception("[scheduler] job FAILED: %s", job_name)


def _hhmm(value: str, default_hour: int = 9, default_minute: int = 0) -> tuple[int, int]:
    """``"HH:MM"`` 형식 파싱. 잘못된 값은 기본값으로 폴백."""
    try:
        hh, mm = value.split(":", 1)
        return max(0, min(23, int(hh))), max(0, min(59, int(mm)))
    except Exception:
        logger.warning(
            "[scheduler] invalid HH:MM=%r → fallback %02d:%02d",
            value,
            default_hour,
            default_minute,
        )
        return default_hour, default_minute


# ---------------------------------------------------------------------------
# 개별 잡 본문
# ---------------------------------------------------------------------------


async def _job_dart() -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.dart_api_key:
        logger.warning("[scheduler] dart_api_key 없음 — DART 잡 스킵")
        return None
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, settings.dart_api_key)
        return await svc.ingest_dart()


async def _job_wowtale() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_wowtale(max_items=50, fetch_article_if_short=True)


async def _job_platum() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_platum(max_items=50, fetch_article_if_short=True)


async def _job_startup_recipe() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_startup_recipe(max_items=50)


async def _job_msit_press() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_msit_press(
            max_pages=6, max_items=100, fetch_body=True
        )


async def _job_msit_biz() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_msit_biz(
            max_pages=6, max_items=100, fetch_body=True
        )


async def _job_msit_rnd_budget() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_msit_rnd_budget(max_pages=2, max_items=20)


async def _job_smes_opportunity() -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.smes_service_key:
        logger.warning("[scheduler] smes_service_key 없음 — SMES 잡 스킵")
        return None
    async with AsyncSessionLocal() as session:
        svc = BronzeOpportunityIngestService(session, settings.smes_service_key)
        return await svc.ingest_smes(max_items=200)


async def _job_alio() -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.alio_service_key:
        logger.warning("[scheduler] alio_service_key 없음 — ALIO 잡 스킵")
        return None
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None, settings.alio_service_key)
        return await svc.ingest_alio_projects(max_items=500)


async def _job_yahoo_finance() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_yahoo_finance(backfill=False, period=None)


async def _job_yahoo_macro() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = BronzeEconomicIngestService(session, None)
        return await svc.ingest_yahoo_macro()


# ---------------------------------------------------------------------------
# 등록 & 라이프사이클
# ---------------------------------------------------------------------------


# (job_id, factory, group)
_DAILY_JOBS: tuple[tuple[str, Callable[[], Awaitable[Any]]], ...] = (
    ("dart",              _job_dart),
    ("wowtale",           _job_wowtale),
    ("platum",            _job_platum),
    ("startup_recipe",    _job_startup_recipe),
    ("msit_press",        _job_msit_press),
    ("msit_biz",          _job_msit_biz),
    ("msit_rnd_budget",   _job_msit_rnd_budget),
    ("smes_opportunity",  _job_smes_opportunity),
)

_WEEKLY_JOBS: tuple[tuple[str, Callable[[], Awaitable[Any]]], ...] = (
    ("alio_projects",  _job_alio),
    ("yahoo_finance",  _job_yahoo_finance),
    ("yahoo_macro",    _job_yahoo_macro),
)


def _wrap(job_name: str, factory: Callable[[], Awaitable[Any]]) -> Callable[[], Awaitable[None]]:
    async def runner() -> None:
        await _run_job(job_name, factory)
    runner.__name__ = f"job_{job_name}"
    return runner


def start_scheduler() -> AsyncIOScheduler | None:
    """FastAPI startup 에서 호출. ``scheduler_enabled=False`` 면 no-op + None 반환."""
    global _scheduler

    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("[scheduler] disabled (SCHEDULER_ENABLED=false)")
        return None
    if _scheduler is not None:
        logger.warning("[scheduler] already started — skip")
        return _scheduler

    try:
        # AsyncIOScheduler 가 현재 실행 중인 루프에 잡을 붙인다 (FastAPI lifespan 안에서 호출).
        asyncio.get_running_loop()
    except RuntimeError:
        logger.error("[scheduler] no running loop — start_scheduler must be called from async context")
        return None

    sched = AsyncIOScheduler(timezone=settings.scheduler_timezone)

    # 일일 잡 — Cron(매일 HH:MM)
    daily_hh, daily_mm = _hhmm(settings.scheduler_daily_at)
    daily_trigger = CronTrigger(
        hour=daily_hh,
        minute=daily_mm,
        timezone=settings.scheduler_timezone,
    )
    for job_id, factory in _DAILY_JOBS:
        sched.add_job(
            _wrap(job_id, factory),
            trigger=daily_trigger,
            id=f"daily_{job_id}",
            name=f"daily_{job_id}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
        )

    # 주간 잡 — Cron(요일 + HH:MM)
    weekly_hh, weekly_mm = _hhmm(settings.scheduler_weekly_at)
    weekly_trigger = CronTrigger(
        day_of_week=settings.scheduler_weekly_dow,
        hour=weekly_hh,
        minute=weekly_mm,
        timezone=settings.scheduler_timezone,
    )
    for job_id, factory in _WEEKLY_JOBS:
        sched.add_job(
            _wrap(job_id, factory),
            trigger=weekly_trigger,
            id=f"weekly_{job_id}",
            name=f"weekly_{job_id}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
        )

    sched.start()
    _scheduler = sched

    logger.info(
        "[scheduler] STARTED tz=%s daily=%02d:%02d weekly=DoW%s %02d:%02d "
        "daily_jobs=%d weekly_jobs=%d",
        settings.scheduler_timezone,
        daily_hh, daily_mm,
        settings.scheduler_weekly_dow,
        weekly_hh, weekly_mm,
        len(_DAILY_JOBS),
        len(_WEEKLY_JOBS),
    )
    for job in sched.get_jobs():
        logger.info("[scheduler] registered: id=%s next_run=%s", job.id, job.next_run_time)
    return sched


def stop_scheduler() -> None:
    """FastAPI shutdown 에서 호출. 진행 중인 잡은 기다리지 않고 즉시 종료(빠른 셧다운)."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] shutdown done")
    except Exception:
        logger.exception("[scheduler] shutdown failed")
    finally:
        _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    """라우터/디버그용 — 현재 살아있는 스케줄러 인스턴스 (없으면 None)."""
    return _scheduler


def list_jobs() -> list[dict[str, Any]]:
    """등록된 잡 메타 + 다음 트리거 시각을 반환 — 헬스/디버그 엔드포인트용."""
    if _scheduler is None:
        return []
    rows: list[dict[str, Any]] = []
    for job in _scheduler.get_jobs():
        rows.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
        )
    return rows


async def run_job_now(job_id: str) -> dict[str, Any]:
    """수동 트리거 — 등록된 ``job_id`` 를 지금 1 회 실행.

    ``daily_*`` / ``weekly_*`` 접두사가 없어도 받을 수 있도록 prefix 보정.
    """
    if _scheduler is None:
        raise RuntimeError("scheduler is not running")
    candidates = (
        job_id,
        f"daily_{job_id}",
        f"weekly_{job_id}",
    )
    job = None
    for cid in candidates:
        job = _scheduler.get_job(cid)
        if job:
            break
    if job is None:
        raise KeyError(f"unknown job_id: {job_id}")

    # APScheduler 가 trigger 없이 한 번만 즉시 실행하도록 modify
    _scheduler.modify_job(job.id, next_run_time=None)  # 일시 정지 대신 즉시 호출
    # job.func 는 이미 _wrap 으로 감싸 예외를 swallow 함
    await job.func()
    return {"job_id": job.id, "status": "ran_now"}


__all__ = [
    "start_scheduler",
    "stop_scheduler",
    "get_scheduler",
    "list_jobs",
    "run_job_now",
]
