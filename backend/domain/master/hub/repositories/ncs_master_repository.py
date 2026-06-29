# NCS 역량 마스터 적재/갱신 리포지토리

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.master.models.bases.ncs_competency_master import NcsCompetencyMaster
from domain.master.models.transfer.ncs_master_dto import NcsMasterDto

_UPDATABLE = (
    "name",
    "level",
    "parent_code",
    "category_l1_code",
    "category_l1_name",
    "category_l2_code",
    "category_l2_name",
    "category_l3_code",
    "category_l3_name",
    "category_l4_code",
    "category_l4_name",
    "description",
    "performance_criteria",
    "knowledge_skills",
    "linked_qualification",
    "raw_metadata",
    "version",
)


def _payload(dto: NcsMasterDto) -> dict[str, Any]:
    return {
        "source_type": dto.source_type[:50],
        "ncs_code": dto.ncs_code[:30],
        "level": dto.level,
        "name": dto.name[:300],
        "parent_code": dto.parent_code,
        "category_l1_code": dto.category_l1_code,
        "category_l1_name": dto.category_l1_name,
        "category_l2_code": dto.category_l2_code,
        "category_l2_name": dto.category_l2_name,
        "category_l3_code": dto.category_l3_code,
        "category_l3_name": dto.category_l3_name,
        "category_l4_code": dto.category_l4_code,
        "category_l4_name": dto.category_l4_name,
        "description": dto.description,
        "performance_criteria": dto.performance_criteria,
        "knowledge_skills": dto.knowledge_skills,
        "linked_qualification": dto.linked_qualification,
        "raw_metadata": dto.raw_metadata,
        "version": dto.version,
    }


class NcsMasterRepository(BaseRepository):
    async def upsert_many(self, rows: list[NcsMasterDto]) -> int:
        seen: set[tuple[str, str]] = set()
        payload: list[dict[str, Any]] = []
        for dto in rows:
            key = (dto.source_type, dto.ncs_code)
            if key in seen:
                continue
            seen.add(key)
            payload.append(_payload(dto))
        if not payload:
            return 0

        def _build(chunk: list[dict[str, Any]]):
            ins = pg_insert(NcsCompetencyMaster).values(chunk)
            update_set = {col: ins.excluded[col] for col in _UPDATABLE}
            update_set["updated_at"] = func.now()
            return ins.on_conflict_do_update(
                constraint="uq_ncs_master_source_code",
                set_=update_set,
            ).returning(NcsCompetencyMaster.id)

        return await self._execute_with_retry(
            lambda: self._commit_batched_returning(_build, payload)
        )

    async def count_by_source_type(self, source_type: str) -> int:
        stmt = select(func.count(NcsCompetencyMaster.id)).where(
            NcsCompetencyMaster.source_type == source_type
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def find_by_parent_code(self, parent_code: str) -> list[NcsCompetencyMaster]:
        stmt = (
            select(NcsCompetencyMaster)
            .where(NcsCompetencyMaster.parent_code == parent_code)
            .order_by(NcsCompetencyMaster.ncs_code)
        )
        return list((await self.session.execute(stmt)).scalars().all())
