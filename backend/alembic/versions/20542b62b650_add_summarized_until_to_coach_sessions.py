"""add summarized_until to coach_sessions

Revision ID: 20542b62b650
Revises: 26149c601ff7
Create Date: 2026-07-02 01:03:14.183641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20542b62b650'
down_revision: Union[str, None] = '26149c601ff7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('coach_sessions', sa.Column('summarized_until', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('coach_sessions', 'summarized_until')
