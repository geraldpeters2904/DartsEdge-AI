"""expand settings

Revision ID: 92bf88ccb571
Revises: 8ac8c1114b16
Create Date: 2026-07-24 09:24:55.182665
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "92bf88ccb571"
down_revision: Union[str, Sequence[str], None] = "8ac8c1114b16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("default_stake_percent", sa.Float(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("kelly_fraction", sa.Float(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("max_daily_risk", sa.Float(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("minimum_edge", sa.Float(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("minimum_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("auto_refresh", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("refresh_interval", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("settings", "refresh_interval")
    op.drop_column("settings", "auto_refresh")
    op.drop_column("settings", "minimum_confidence")
    op.drop_column("settings", "minimum_edge")
    op.drop_column("settings", "max_daily_risk")
    op.drop_column("settings", "kelly_fraction")
    op.drop_column("settings", "default_stake_percent")