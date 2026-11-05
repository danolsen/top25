"""Allow tied official ranks and remember poll order."""

import sqlalchemy as sa
from alembic import op

revision = "002_official_ties"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("official_entries")}
    if "position" not in columns:
        op.add_column("official_entries", sa.Column("position", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE official_entries SET position = rank WHERE placement = 'ranked' AND position IS NULL AND rank IS NOT NULL"
        )
    )
    names = {constraint["name"] for constraint in inspector.get_unique_constraints("official_entries")}
    if "uq_official_rank" in names:
        op.drop_constraint("uq_official_rank", "official_entries", type_="unique")
    names = {constraint["name"] for constraint in sa.inspect(bind).get_unique_constraints("official_entries")}
    if "uq_official_position" not in names:
        op.create_unique_constraint("uq_official_position", "official_entries", ["poll_id", "position"])


def downgrade() -> None:
    bind = op.get_bind()
    names = {constraint["name"] for constraint in sa.inspect(bind).get_unique_constraints("official_entries")}
    if "uq_official_position" in names:
        op.drop_constraint("uq_official_position", "official_entries", type_="unique")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("official_entries")}
    if "position" in columns:
        op.drop_column("official_entries", "position")
    names = {constraint["name"] for constraint in sa.inspect(bind).get_unique_constraints("official_entries")}
    if "uq_official_rank" not in names:
        op.create_unique_constraint("uq_official_rank", "official_entries", ["poll_id", "rank"])
