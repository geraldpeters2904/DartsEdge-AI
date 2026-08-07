"""add player career profile cache

Revision ID: e6f3b7a91c20
Revises: 12799efbfd56
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa


revision = "e6f3b7a91c20"
down_revision = "12799efbfd56"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "player_career_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column(
            "competition_code",
            sa.String(length=40),
            nullable=False,
            server_default="ALL",
        ),
        sa.Column(
            "matches_played",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "wins",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "losses",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "win_percentage",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "legs_won",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "legs_lost",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "leg_difference",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "average_three_dart_average",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "average_first_nine_average",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "scores_100_plus",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "scores_140_plus",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "scores_180",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "maximums_per_match",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "checkout_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "checkouts_completed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "calculated_checkout_percentage",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "average_reported_checkout_percentage",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "highest_checkout",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "recent_form_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("first_match_date", sa.Date(), nullable=True),
        sa.Column("latest_match_date", sa.Date(), nullable=True),
        sa.Column(
            "refreshed_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "competition_code",
            name="uq_player_career_profile_scope",
        ),
    )
    op.create_index(
        "ix_player_career_profiles_id",
        "player_career_profiles",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_player_career_profiles_player_id",
        "player_career_profiles",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        "ix_player_career_profiles_competition_code",
        "player_career_profiles",
        ["competition_code"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_player_career_profiles_competition_code",
        table_name="player_career_profiles",
    )
    op.drop_index(
        "ix_player_career_profiles_player_id",
        table_name="player_career_profiles",
    )
    op.drop_index(
        "ix_player_career_profiles_id",
        table_name="player_career_profiles",
    )
    op.drop_table("player_career_profiles")
