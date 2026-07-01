"""add user_self_model and evidence

Revision ID: b4cb00cc6a07
Revises: a3f7c1e9d2b4
Create Date: 2026-07-01 17:44:32.613972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b4cb00cc6a07'
down_revision: Union[str, None] = 'a3f7c1e9d2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_self_model',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('riasec', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('big_five', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('narrative_summary', sa.Text(), nullable=True),
    sa.Column('axis_confidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('source', sa.String(length=30), server_default='coach_extraction', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_user_self_model_user', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id'),
    comment='자기모델 구조 척추 — RIASEC·Big Five·자기서사(coach 추출/폼)'
    )
    op.create_table('user_self_model_evidence',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('dimension', sa.String(length=30), nullable=False),
    sa.Column('polarity', sa.String(length=10), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('confidence', sa.Numeric(precision=3, scale=2), nullable=True),
    sa.Column('is_sensitive', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('coach_session_ref', sa.String(length=64), nullable=True),
    sa.Column('source', sa.String(length=30), server_default='coach_extraction', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_self_model_evidence_user', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'content_hash', name='uq_self_model_evidence_dedup'),
    comment='자기모델 근거 — 대화 추출 호불호·제약·민감정보(append-only, dedup)'
    )
    op.create_index('ix_self_model_evidence_user', 'user_self_model_evidence', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_self_model_evidence_user', table_name='user_self_model_evidence')
    op.drop_table('user_self_model_evidence')
    op.drop_table('user_self_model')
