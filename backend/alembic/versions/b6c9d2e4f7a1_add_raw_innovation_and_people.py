"""혁신 및 사람 수요 Bronze 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b6c9d2e4f7a1"
down_revision: Union[str, None] = "a3f8c2d1e9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_innovation_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("author_or_assignee", sa.String(length=255), nullable=True),
        sa.Column("abstract_text", sa.Text(), nullable=True),
        sa.Column("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_url", name="uq_raw_innovation_data_source_url"),
        comment="Bronze — 특허·논문·오픈소스 등 혁신 흐름 원천",
    )
    op.create_index(
        "ix_raw_innovation_source_type_published_at",
        "raw_innovation_data",
        ["source_type", "published_at"],
    )

    op.create_table(
        "raw_people_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("keyword_or_job", sa.String(length=100), nullable=False),
        sa.Column("search_volume_or_count", sa.Integer(), nullable=True),
        sa.Column("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reference_date", sa.Date(), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "keyword_or_job",
            "reference_date",
            name="uq_raw_people_data_source_keyword_date",
        ),
        comment="Bronze — 검색량·채용·훈련 수요 등 사람·역량 수요 원천",
    )
    op.create_index(
        "ix_raw_people_source_type_reference_date",
        "raw_people_data",
        ["source_type", "reference_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_people_source_type_reference_date", table_name="raw_people_data")
    op.drop_table("raw_people_data")
    op.drop_index(
        "ix_raw_innovation_source_type_published_at", table_name="raw_innovation_data"
    )
    op.drop_table("raw_innovation_data")

