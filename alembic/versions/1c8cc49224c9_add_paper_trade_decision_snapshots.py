"""add paper trade decision snapshots

Revision ID: 1c8cc49224c9
Revises: f7a4c8d21e30
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = "1c8cc49224c9"
down_revision = "f7a4c8d21e30"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("paper_trades") as batch_op:
        batch_op.add_column(
            sa.Column(
                "model_probability",
                sa.Float(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "expected_value",
                sa.Float(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "suggested_stake",
                sa.Float(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "strategy_name",
                sa.String(),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("paper_trades") as batch_op:
        batch_op.drop_column("strategy_name")
        batch_op.drop_column("suggested_stake")
        batch_op.drop_column("expected_value")
        batch_op.drop_column("model_probability")
