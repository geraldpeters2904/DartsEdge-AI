"""add fixture id to paper trades

Revision ID: 7b2d4e6f8a10
Revises: 1c8cc49224c9
Create Date: 2026-09-02

"""

from alembic import op
import sqlalchemy as sa


revision = "7b2d4e6f8a10"
down_revision = "1c8cc49224c9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("paper_trades") as batch_op:
        batch_op.add_column(
            sa.Column(
                "fixture_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_paper_trades_fixture_id_matches",
            "matches",
            ["fixture_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_paper_trades_fixture_id",
            ["fixture_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("paper_trades") as batch_op:
        batch_op.drop_index("ix_paper_trades_fixture_id")
        batch_op.drop_constraint(
            "fk_paper_trades_fixture_id_matches",
            type_="foreignkey",
        )
        batch_op.drop_column("fixture_id")
