"""add scheduled at to matches

Revision ID: 9d4c6a8e2f31
Revises: 7b2d4e6f8a10
Create Date: 2026-09-10

"""

from alembic import op
import sqlalchemy as sa


revision = "9d4c6a8e2f31"
down_revision = "7b2d4e6f8a10"
branch_labels = None
depends_on = None


def upgrade():

    with op.batch_alter_table("matches") as batch_op:

        batch_op.add_column(
            sa.Column(
                "scheduled_at",
                sa.DateTime(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_matches_scheduled_at",
            ["scheduled_at"],
            unique=False,
        )


def downgrade():

    with op.batch_alter_table("matches") as batch_op:

        batch_op.drop_index(
            "ix_matches_scheduled_at"
        )

        batch_op.drop_column(
            "scheduled_at"
        )
