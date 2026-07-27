"""add player match performance warehouse

Revision ID: d4b1a2c3e4f5
Revises: 92bf88ccb571
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4b1a2c3e4f5"
down_revision: Union[str, Sequence[str], None] = (
    "92bf88ccb571"
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("player_match_performances"):
        return

    op.create_table(
        "player_match_performances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("opponent_id", sa.Integer(), nullable=True),
        sa.Column(
            "competition_code",
            sa.String(length=40),
            nullable=True,
        ),
        sa.Column(
            "player_external_id",
            sa.String(length=160),
            nullable=True,
        ),
        sa.Column("won_match", sa.Boolean(), nullable=True),
        sa.Column("threw_first", sa.Boolean(), nullable=True),
        sa.Column("legs_won", sa.Integer(), nullable=True),
        sa.Column("legs_lost", sa.Integer(), nullable=True),
        sa.Column("legs_held", sa.Integer(), nullable=True),
        sa.Column("legs_broken", sa.Integer(), nullable=True),
        sa.Column(
            "three_dart_average",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "first_nine_average",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "scores_100_plus",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "scores_140_plus",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column("scores_180", sa.Integer(), nullable=True),
        sa.Column(
            "checkout_attempts",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "checkouts_completed",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "checkout_percentage",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "highest_checkout",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "match_duration_seconds",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "source_provider",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "source_external_id",
            sa.String(length=160),
            nullable=True,
        ),
        sa.Column(
            "source_confidence",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "observed_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
        ),
        sa.ForeignKeyConstraint(
            ["opponent_id"],
            ["players.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "match_id",
            "player_id",
            name="uq_player_match_performance",
        ),
    )

    indexed_columns = (
        "id",
        "match_id",
        "player_id",
        "opponent_id",
        "competition_code",
        "player_external_id",
        "source_provider",
    )

    for column_name in indexed_columns:
        op.create_index(
            f"ix_player_match_performances_{column_name}",
            "player_match_performances",
            [column_name],
            unique=False,
        )

    op.create_index(
        "ix_player_match_performance_player_created",
        "player_match_performances",
        ["player_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_player_match_performance_competition_player",
        "player_match_performances",
        ["competition_code", "player_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("player_match_performances"):
        op.drop_table("player_match_performances")
