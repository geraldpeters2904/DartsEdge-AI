"""add decision safety to opportunity snapshots

Revision ID: f7a4c8d21e30
Revises: e6f3b7a91c20
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa


revision = "f7a4c8d21e30"
down_revision = "e6f3b7a91c20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "opportunity_snapshots"
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "decision_safety_state",
                sa.String(),
                nullable=False,
                server_default="UNKNOWN",
            )
        )

        batch_op.add_column(
            sa.Column(
                "decision_safety_explanation",
                sa.String(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "sparse_consensus_density",
                sa.Float(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "sparse_consensus_risk_state",
                sa.String(),
                nullable=False,
                server_default="UNKNOWN",
            )
        )


def downgrade():
    with op.batch_alter_table(
        "opportunity_snapshots"
    ) as batch_op:
        batch_op.drop_column(
            "sparse_consensus_risk_state"
        )

        batch_op.drop_column(
            "sparse_consensus_density"
        )

        batch_op.drop_column(
            "decision_safety_explanation"
        )

        batch_op.drop_column(
            "decision_safety_state"
        )
