"""merge raw_tech_adoption_data and sentiment branches

Revision ID: d1a2b3c4e5f6
Revises: c7e3a9f1b5d2, a9d2f7c4e1b8
Create Date: 2026-06-29

"""
from typing import Sequence, Union

revision: str = 'd1a2b3c4e5f6'
down_revision: Union[str, tuple[str, ...], None] = ('c7e3a9f1b5d2', 'a9d2f7c4e1b8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
