"""Add Bet Slip stake authorisation classification.

Revision ID: a7c9e2d4b601
Revises: 9d4c6a8e2f31
"""

from alembic import op
import sqlalchemy as sa

revision = "a7c9e2d4b601"
down_revision = "9d4c6a8e2f31"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bet_slip_items",
        sa.Column(
            "stake_source",
            sa.String(),
            nullable=False,
            server_default="unverified",
        ),
    )


def downgrade():
    op.drop_column("bet_slip_items", "stake_source")
