# 로드맵 생성 런 리포지토리 — 활성 run 유니크 보장·stale lazy 마킹·진행률 갱신
from __future__ import annotations

import json
import uuid

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_STALE_MINUTES = 10

_INSERT_RUN = text(
    """
    INSERT INTO roadmap_generation_runs (run_id, user_id, status, trigger, started_at, updated_at)
    VALUES (CAST(:run_id AS UUID), CAST(:user_id AS UUID), 'running', :trigger, now(), now())
    ON CONFLICT (user_id) WHERE status IN ('pending','running') DO NOTHING
    RETURNING run_id, status, trigger
    """
)

_MARK_STALE = text(
    """
    UPDATE roadmap_generation_runs
    SET status = 'failed', error = 'stale', finished_at = now(), updated_at = now()
    WHERE user_id = CAST(:user_id AS UUID)
      AND status IN ('pending','running')
      AND updated_at < now() - make_interval(mins => :stale_min)
    """
)

_FETCH_LATEST = text(
    """
    SELECT run_id, status, trigger, progress, result, error, started_at, finished_at
    FROM roadmap_generation_runs
    WHERE user_id = CAST(:user_id AS UUID)
    ORDER BY id DESC
    LIMIT 1
    """
)

_UPDATE_PROGRESS = text(
    """
    UPDATE roadmap_generation_runs
    SET progress = CAST(:progress AS JSONB), updated_at = now()
    WHERE run_id = CAST(:run_id AS UUID)
    """
)

_FINISH_RUN = text(
    """
    UPDATE roadmap_generation_runs
    SET status = :status, result = CAST(:result AS JSONB), error = :error,
        finished_at = now(), updated_at = now()
    WHERE run_id = CAST(:run_id AS UUID)
    """
)


def _row_to_dict(r) -> dict:
    return {
        "run_id": str(r.run_id),
        "status": r.status,
        "trigger": r.trigger,
        "progress": r.progress,
        "result": r.result,
        "error": r.error,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


class GenerationRunRepository(BaseRepository):
    async def create_run(self, user_id: str, trigger: str) -> dict | None:
        """활성 run이 없으면 running 으로 생성. 있으면 None(이미 진행 중)."""
        # 좀비가 자리를 차지하지 않도록 생성 직전에 stale 정리.
        await self.session.execute(
            _MARK_STALE, {"user_id": user_id, "stale_min": _STALE_MINUTES}
        )
        row = (
            await self.session.execute(
                _INSERT_RUN,
                {"run_id": str(uuid.uuid4()), "user_id": user_id, "trigger": trigger},
            )
        ).first()
        await self.session.commit()
        if row is None:
            return None
        return {"run_id": str(row.run_id), "status": row.status, "trigger": row.trigger}

    async def fetch_latest(self, user_id: str) -> dict | None:
        """최근 run 1건 — 조회 시점에 stale run 을 failed 로 lazy 마킹한다."""
        await self.session.execute(
            _MARK_STALE, {"user_id": user_id, "stale_min": _STALE_MINUTES}
        )
        await self.session.commit()
        r = (await self.session.execute(_FETCH_LATEST, {"user_id": user_id})).first()
        return _row_to_dict(r) if r else None

    async def update_progress(self, run_id: str, progress: dict) -> None:
        await self.session.execute(
            _UPDATE_PROGRESS, {"run_id": run_id, "progress": json.dumps(progress, ensure_ascii=False)}
        )
        await self.session.commit()

    async def finish(
        self, run_id: str, status: str, result: dict | None = None, error: str | None = None
    ) -> None:
        await self.session.execute(
            _FINISH_RUN,
            {
                "run_id": run_id,
                "status": status,
                "result": json.dumps(result, ensure_ascii=False) if result else None,
                "error": error,
            },
        )
        await self.session.commit()
