"""Persist SwissAI route/stream facts and index per-key history reads."""

import sqlalchemy as sa
from alembic import op

revision = "20261028_010000_add_swissai_request_metadata"
down_revision = "20261028_000000_add_swissai_key_pool"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("request_logs")}
    with op.batch_alter_table("request_logs") as batch:
        if "route" not in columns:
            batch.add_column(sa.Column("route", sa.String(128), nullable=True))
        if "stream" not in columns:
            batch.add_column(sa.Column("stream", sa.Boolean(), nullable=True))
    op.create_index("ix_logs_source_requested", "request_logs", ["model_source_id", "requested_at"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_logs_source_requested", table_name="request_logs", if_exists=True)
    with op.batch_alter_table("request_logs") as batch:
        batch.drop_column("stream")
        batch.drop_column("route")
