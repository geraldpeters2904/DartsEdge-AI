"""Allow fixture-based paper trades without a synthetic prediction.

Revision ID: c9e4a2b7d103
Revises: b8d3f1a6c902
"""

from alembic import op

revision = "c9e4a2b7d103"
down_revision = "b8d3f1a6c902"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("paper_trades") as batch_op:
        batch_op.alter_column(
            "prediction_id",
            existing_type=__import__("sqlalchemy").Integer(),
            existing_nullable=False,
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table("paper_trades") as batch_op:
        batch_op.alter_column(
            "prediction_id",
            existing_type=__import__("sqlalchemy").Integer(),
            existing_nullable=True,
            nullable=False,
        )
