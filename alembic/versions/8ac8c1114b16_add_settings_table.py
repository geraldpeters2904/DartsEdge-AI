"""add settings table

Revision ID: 8ac8c1114b16
Revises:
Create Date: 2026-07-24 08:59:26.157630
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8ac8c1114b16"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bankroll", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_settings_id"),
        "settings",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_settings_id"),
        table_name="settings",
    )

    op.drop_table("settings")