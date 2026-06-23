"""임시 PostgreSQL 테이블로 혁신·사람 Repository 멱등 적재를 검증한다."""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.database import engine  # noqa: E402
from domain.master.hub.repositories.innovation_repository import InnovationRepository  # noqa: E402
from domain.master.hub.repositories.people_repository import PeopleRepository  # noqa: E402
from domain.master.models.transfer.innovation_collect_dto import InnovationCollectDto  # noqa: E402
from domain.master.models.transfer.people_collect_dto import PeopleCollectDto  # noqa: E402


async def main() -> int:
    async with engine.connect() as connection:
        await connection.execute(
            text(
                """
                CREATE TEMP TABLE raw_innovation_data (
                    id BIGSERIAL PRIMARY KEY,
                    source_type VARCHAR(50) NOT NULL,
                    source_url TEXT,
                    title VARCHAR(500) NOT NULL,
                    author_or_assignee VARCHAR(255),
                    abstract_text TEXT,
                    raw_metadata JSONB,
                    published_at TIMESTAMPTZ,
                    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_raw_innovation_data_source_url UNIQUE (source_url)
                )
                """
            )
        )
        await connection.execute(
            text(
                """
                CREATE TEMP TABLE raw_people_data (
                    id BIGSERIAL PRIMARY KEY,
                    source_type VARCHAR(50) NOT NULL,
                    source_url TEXT,
                    keyword_or_job VARCHAR(100) NOT NULL,
                    search_volume_or_count INT,
                    raw_metadata JSONB,
                    reference_date DATE,
                    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_raw_people_data_source_keyword_date
                        UNIQUE (source_type, keyword_or_job, reference_date)
                )
                """
            )
        )
        await connection.commit()

        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            innovation_repo = InnovationRepository(session)
            innovation = InnovationCollectDto(
                source_type="INNOVATION_ARXIV_KR",
                source_url="https://arxiv.org/abs/test",
                title="Test paper",
                raw_metadata={"week_start": "20260608"},
                published_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
            )
            first = await innovation_repo.insert_many_skip_duplicates([innovation])
            duplicate = await innovation_repo.insert_many_skip_duplicates([innovation])
            latest = await innovation_repo.latest_by_source_type("INNOVATION_ARXIV_KR")

            people_repo = PeopleRepository(session)
            people = PeopleCollectDto(
                source_type="PEOPLE_WORKNET_JOB",
                source_url="https://example.test",
                keyword_or_job="개발자",
                search_volume_or_count=10,
                reference_date=date(2026, 6, 8),
            )
            people_first = await people_repo.insert_many_skip_duplicates([people])
            people_duplicate = await people_repo.insert_many_skip_duplicates([people])
            latest_date = await people_repo.latest_reference_date("PEOPLE_WORKNET_JOB")

        result = {
            "innovation": (first, duplicate, latest is not None),
            "people": (people_first, people_duplicate, str(latest_date)),
        }
        print(result)
        ok = result == {
            "innovation": (1, 0, True),
            "people": (1, 0, "2026-06-08"),
        }

    await engine.dispose()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

