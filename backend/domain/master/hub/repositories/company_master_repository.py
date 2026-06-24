"""검증 기업 마스터(verified_company_master)의 적재·갱신을 담당한다.

벤처기업명단처럼 사업자번호가 없는 출처가 있어 두 경로로 멱등성을 보장한다.
  - business_number 有: (source_type, business_number) ON CONFLICT DO UPDATE
  - business_number 無: (source_type, company_name) 기준 신규만 INSERT (재실행 시 중복 방지)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.auth.hub.repositories.base_repository import BaseRepository
from domain.master.models.bases.verified_company_master import VerifiedCompanyMaster
from domain.master.models.transfer.company_master_dto import CompanyMasterDto

# ON CONFLICT DO UPDATE 시 갱신할 컬럼 (식별 키·collected_at 제외).
_UPDATABLE = (
    "company_name",
    "corp_number",
    "ceo_name",
    "certification_type",
    "certification_date",
    "expiry_date",
    "certifying_agency",
    "industry_sector",
    "establishment_date",
    "address",
    "raw_metadata",
    "source_file_url",
    "source_file_version",
)


def _payload(dto: CompanyMasterDto) -> dict[str, Any]:
    return {
        "source_type": dto.source_type[:50],
        "company_name": dto.company_name[:255],
        "business_number": dto.business_number,
        "corp_number": dto.corp_number,
        "ceo_name": dto.ceo_name,
        "certification_type": dto.certification_type,
        "certification_date": dto.certification_date,
        "expiry_date": dto.expiry_date,
        "certifying_agency": dto.certifying_agency,
        "industry_sector": dto.industry_sector,
        "establishment_date": dto.establishment_date,
        "address": dto.address,
        "raw_metadata": dto.raw_metadata,
        "source_file_url": dto.source_file_url,
        "source_file_version": dto.source_file_version,
    }


class CompanyMasterRepository(BaseRepository):
    async def upsert_many(self, rows: list[CompanyMasterDto]) -> dict[str, int]:
        with_bn = [r for r in rows if (r.business_number or "").strip()]
        without_bn = [r for r in rows if not (r.business_number or "").strip()]
        upserted = await self._upsert_with_business_number(with_bn)
        inserted_new = await self._insert_new_without_business_number(without_bn)
        return {
            "upserted": upserted,
            "inserted_new": inserted_new,
            "total": len(rows),
        }

    async def _upsert_with_business_number(self, rows: list[CompanyMasterDto]) -> int:
        seen: set[tuple[str, str]] = set()
        payload: list[dict[str, Any]] = []
        for dto in rows:
            key = (dto.source_type, (dto.business_number or "").strip())
            if key in seen:
                continue
            seen.add(key)
            payload.append(_payload(dto))
        if not payload:
            return 0

        def _build(chunk: list[dict[str, Any]]):
            ins = pg_insert(VerifiedCompanyMaster).values(chunk)
            update_set = {col: ins.excluded[col] for col in _UPDATABLE}
            update_set["updated_at"] = func.now()
            return ins.on_conflict_do_update(
                index_elements=["source_type", "business_number"],
                index_where=text("business_number IS NOT NULL"),
                set_=update_set,
            ).returning(VerifiedCompanyMaster.id)

        return await self._execute_with_retry(
            lambda: self._commit_batched_returning(_build, payload)
        )

    async def _insert_new_without_business_number(
        self, rows: list[CompanyMasterDto]
    ) -> int:
        if not rows:
            return 0
        source_types = {r.source_type for r in rows}

        async def _load_existing() -> set[tuple[str, str]]:
            stmt = select(
                VerifiedCompanyMaster.source_type, VerifiedCompanyMaster.company_name
            ).where(
                VerifiedCompanyMaster.source_type.in_(source_types),
                VerifiedCompanyMaster.business_number.is_(None),
            )
            result = await self.session.execute(stmt)
            return {(st, nm) for st, nm in result.all()}

        existing = await self._execute_with_retry(_load_existing)

        seen: set[tuple[str, str]] = set()
        payload: list[dict[str, Any]] = []
        for dto in rows:
            key = (dto.source_type, dto.company_name[:255])
            if key in existing or key in seen:
                continue
            seen.add(key)
            payload.append(_payload(dto))
        if not payload:
            return 0

        def _build(chunk: list[dict[str, Any]]):
            return pg_insert(VerifiedCompanyMaster).values(chunk).returning(
                VerifiedCompanyMaster.id
            )

        return await self._execute_with_retry(
            lambda: self._commit_batched_returning(_build, payload)
        )

    async def count_by_source_type(self, source_type: str) -> int:
        stmt = select(func.count(VerifiedCompanyMaster.id)).where(
            VerifiedCompanyMaster.source_type == source_type
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)
