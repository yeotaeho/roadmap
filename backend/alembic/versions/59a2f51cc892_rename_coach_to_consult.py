"""rename coach to consult

Revision ID: 59a2f51cc892
Revises: a6af4387ed37
Create Date: 2026-07-03 01:48:42.985327

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59a2f51cc892'
down_revision: Union[str, None] = 'a6af4387ed37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("coach_sessions", "consult_sessions")
    op.rename_table("coach_messages", "consult_messages")
    op.execute("ALTER INDEX ix_coach_sessions_user RENAME TO ix_consult_sessions_user")
    op.execute("ALTER INDEX ix_coach_messages_session RENAME TO ix_consult_messages_session")
    op.execute("ALTER TABLE consult_sessions RENAME CONSTRAINT fk_coach_session_user TO fk_consult_session_user")
    op.execute("ALTER TABLE consult_messages RENAME CONSTRAINT fk_coach_message_session TO fk_consult_message_session")
    op.alter_column("user_self_model_evidence", "coach_session_ref", new_column_name="consult_session_ref")
    op.execute("UPDATE user_self_model SET source = 'consult_extraction' WHERE source = 'coach_extraction'")
    op.execute("UPDATE user_self_model_evidence SET source = 'consult_extraction' WHERE source = 'coach_extraction'")


def downgrade() -> None:
    op.execute("UPDATE user_self_model_evidence SET source = 'coach_extraction' WHERE source = 'consult_extraction'")
    op.execute("UPDATE user_self_model SET source = 'coach_extraction' WHERE source = 'consult_extraction'")
    op.alter_column("user_self_model_evidence", "consult_session_ref", new_column_name="coach_session_ref")
    op.execute("ALTER TABLE consult_messages RENAME CONSTRAINT fk_consult_message_session TO fk_coach_message_session")
    op.execute("ALTER TABLE consult_sessions RENAME CONSTRAINT fk_consult_session_user TO fk_coach_session_user")
    op.execute("ALTER INDEX ix_consult_messages_session RENAME TO ix_coach_messages_session")
    op.execute("ALTER INDEX ix_consult_sessions_user RENAME TO ix_coach_sessions_user")
    op.rename_table("consult_messages", "coach_messages")
    op.rename_table("consult_sessions", "coach_sessions")

