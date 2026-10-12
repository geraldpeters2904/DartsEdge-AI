"""Add Paper Trade stake authorisation classification.

Revision ID: b8d3f1a6c902
Revises: a7c9e2d4b601
"""

from alembic import op
import sqlalchemy as sa

revision = "b8d3f1a6c902"
down_revision = "a7c9e2d4b601"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "paper_trades",
        sa.Column(
            "stake_source",
            sa.String(),
            nullable=False,
            server_default="unverified",
        ),
    )


def downgrade():
    op.drop_column("paper_trades", "stake_source")
