"""add axis_source to self model

Revision ID: 51f3d7e2ef01
Revises: 59a2f51cc892
Create Date: 2026-07-03 16:57:56.484843

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '51f3d7e2ef01'
down_revision: Union[str, None] = '59a2f51cc892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_self_model",
        sa.Column("axis_source", postgresql.JSONB, nullable=True,
                  comment="축별 출처 — user_form 으로 확정한 축만 기록"),
    )
    # 구 도식의 행 단위 source='user_form' 행을 축별 provenance 로 승격 — 실제 값이 있는 축만.
    op.execute(
        "UPDATE user_self_model SET axis_source = ("
        "(CASE WHEN riasec IS NOT NULL THEN jsonb_build_object('riasec','user_form') ELSE '{}'::jsonb END) "
        "|| (CASE WHEN big_five IS NOT NULL THEN jsonb_build_object('big_five','user_form') ELSE '{}'::jsonb END) "
        "|| (CASE WHEN narrative_summary IS NOT NULL THEN jsonb_build_object('narrative_summary','user_form') ELSE '{}'::jsonb END)"
        ") WHERE source = 'user_form'"
    )


def downgrade() -> None:
    op.drop_column("user_self_model", "axis_source")

