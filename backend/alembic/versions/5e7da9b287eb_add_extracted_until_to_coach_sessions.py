"""add extracted_until to coach_sessions

Revision ID: 5e7da9b287eb
Revises: 20542b62b650
Create Date: 2026-07-02 09:12:01.182422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5e7da9b287eb'
down_revision: Union[str, None] = '20542b62b650'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('coach_sessions', sa.Column('extracted_until', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('coach_sessions', 'extracted_until')
