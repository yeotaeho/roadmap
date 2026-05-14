"""raw_economic_data.source_url UNIQUE — ON CONFLICT 중복 방지용."""

from typing import Sequence, Union

from alembic import op


revision: str = "d4e8f1a2b3c5"
down_revision: Union[str, None] = "fa5b6fba5c4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM raw_economic_data a
        USING raw_economic_data b
        WHERE a.source_url IS NOT NULL
          AND a.source_url = b.source_url
          AND a.id > b.id;
        """
    )
    op.create_unique_constraint(
        "uq_raw_economic_data_source_url",
        "raw_economic_data",
        ["source_url"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_raw_economic_data_source_url", "raw_economic_data", type_="unique")
