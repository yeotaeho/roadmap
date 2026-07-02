"""add explanation columns to sync chance gold

Revision ID: a6af4387ed37
Revises: 5e7da9b287eb
Create Date: 2026-07-02 14:18:02.224076

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a6af4387ed37'
down_revision: Union[str, None] = '5e7da9b287eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sync_scores_daily', sa.Column('explanation', sa.Text(), nullable=True, comment='LLM 생성 추천 설명(없으면 결정론 폴백 표시)'))
    op.add_column('user_chance_matches', sa.Column('match_explanation', sa.Text(), nullable=True, comment='LLM 생성 매칭 설명(match_reason 은 결정론 폴백)'))


def downgrade() -> None:
    op.drop_column('user_chance_matches', 'match_explanation')
    op.drop_column('sync_scores_daily', 'explanation')
