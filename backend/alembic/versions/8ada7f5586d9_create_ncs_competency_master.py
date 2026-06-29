"""create ncs_competency_master

Revision ID: 8ada7f5586d9
Revises: 3d459abe4fb1
Create Date: 2026-06-29 15:38:31.390391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8ada7f5586d9'
down_revision: Union[str, None] = '3d459abe4fb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ncs_competency_master',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('source_type', sa.String(length=50), nullable=False, comment='NCS_CLASSIFICATION / NCS_COMPETENCY_UNIT / NCS_COMPETENCY_ELEMENT'),
    sa.Column('ncs_code', sa.String(length=30), nullable=False, comment='역량단위코드 또는 분류코드'),
    sa.Column('level', sa.SmallInteger(), nullable=False, comment='위계 깊이 (1=대분류 ~ 6=능력단위요소)'),
    sa.Column('name', sa.String(length=300), nullable=False, comment='분류명 또는 역량단위명'),
    sa.Column('parent_code', sa.String(length=30), nullable=True, comment='상위 ncs_code (L1은 NULL)'),
    sa.Column('category_l1_code', sa.String(length=10), nullable=True),
    sa.Column('category_l1_name', sa.String(length=100), nullable=True),
    sa.Column('category_l2_code', sa.String(length=10), nullable=True),
    sa.Column('category_l2_name', sa.String(length=100), nullable=True),
    sa.Column('category_l3_code', sa.String(length=10), nullable=True),
    sa.Column('category_l3_name', sa.String(length=100), nullable=True),
    sa.Column('category_l4_code', sa.String(length=10), nullable=True),
    sa.Column('category_l4_name', sa.String(length=100), nullable=True),
    sa.Column('description', sa.Text(), nullable=True, comment='능력단위 정의'),
    sa.Column('performance_criteria', sa.Text(), nullable=True, comment='수행준거'),
    sa.Column('knowledge_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='지식·기술·태도 목록'),
    sa.Column('linked_qualification', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='연계 자격 정보 (15063879 보충)'),
    sa.Column('raw_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='API 원본 부가정보'),
    sa.Column('version', sa.String(length=20), nullable=True, comment='NCS 버전 (예: v4)'),
    sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_type', 'ncs_code', name='uq_ncs_master_source_code'),
    comment='NCS 직무-역량 온톨로지 마스터 (정적, UPSERT)'
    )
    op.create_index('ix_ncs_master_l1_code', 'ncs_competency_master', ['category_l1_code'], unique=False)
    op.create_index('ix_ncs_master_level', 'ncs_competency_master', ['level'], unique=False)
    op.create_index('ix_ncs_master_parent_code', 'ncs_competency_master', ['parent_code'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ncs_master_parent_code', table_name='ncs_competency_master')
    op.drop_index('ix_ncs_master_level', table_name='ncs_competency_master')
    op.drop_index('ix_ncs_master_l1_code', table_name='ncs_competency_master')
    op.drop_table('ncs_competency_master')
