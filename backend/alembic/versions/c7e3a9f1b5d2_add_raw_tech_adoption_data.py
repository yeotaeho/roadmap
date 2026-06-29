"""add_raw_tech_adoption_data

Revision ID: c7e3a9f1b5d2
Revises: 8ada7f5586d9
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c7e3a9f1b5d2'
down_revision: Union[str, None] = '8ada7f5586d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'raw_tech_adoption_data',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ecosystem', sa.String(length=10), nullable=False, comment='npm | pypi | hf'),
        sa.Column('package_name', sa.String(length=200), nullable=False, comment='패키지명 또는 HuggingFace 모델 ID'),
        sa.Column('sector', sa.String(length=50), nullable=False, comment='FRONTEND / AI_ML / DEVOPS / MOBILE / STYLING / BACKEND 등'),
        sa.Column('weekly_downloads', sa.BigInteger(), nullable=True, comment='주간 다운로드 수 (HF trending은 NULL 가능)'),
        sa.Column('week_start_date', sa.Date(), nullable=False, comment='해당 주 월요일 (ISO 8601 기준)'),
        sa.Column('raw_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='부가정보: hf={downloads_alltime, trending_rank, pipeline_tag}, npm={detail_url}'),
        sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ecosystem', 'package_name', 'week_start_date', name='uq_raw_tech_adoption_ecosystem_pkg_week'),
        comment='Bronze — npm/PyPI/HuggingFace 기술 채택 주간 스냅샷',
    )
    op.create_index('ix_raw_tech_adoption_ecosystem_week', 'raw_tech_adoption_data', ['ecosystem', 'week_start_date'])
    op.create_index('ix_raw_tech_adoption_sector_week', 'raw_tech_adoption_data', ['sector', 'week_start_date'])


def downgrade() -> None:
    op.drop_index('ix_raw_tech_adoption_sector_week', table_name='raw_tech_adoption_data')
    op.drop_index('ix_raw_tech_adoption_ecosystem_week', table_name='raw_tech_adoption_data')
    op.drop_table('raw_tech_adoption_data')
