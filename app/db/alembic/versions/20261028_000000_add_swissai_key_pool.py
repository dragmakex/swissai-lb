"""SwissAI bearer credential health, admission leases, attempts and continuation ownership."""

import sqlalchemy as sa
from alembic import op

revision = "20261028_000000_add_swissai_key_pool"
down_revision = "20260918_000000_merge_scim_and_overflow_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ledger recovery can revisit a complete fresh-fork schema; drift checks still validate its shape.
    op.create_table(
        "swissai_key_state",
        sa.Column("source_id", sa.String(), sa.ForeignKey("model_sources.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("fingerprint", sa.String(64), unique=True, nullable=False),
        sa.Column("key_prefix", sa.String(32), nullable=False),
        sa.Column("invalid_at", sa.DateTime()),
        sa.Column("cooldown_until", sa.DateTime()),
        sa.Column("failure_reason", sa.String(80)),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_selected_at", sa.DateTime()),
        sa.Column("last_success_at", sa.DateTime()),
        sa.Column("last_failure_at", sa.DateTime()),
        if_not_exists=True,
    )
    op.create_table(
        "swissai_leases",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source_id", sa.String(), sa.ForeignKey("swissai_key_state.source_id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        if_not_exists=True,
    )
    op.create_index(
        "ix_swissai_leases_source_expiry", "swissai_leases", ["source_id", "expires_at"], if_not_exists=True
    )
    op.create_table(
        "swissai_attempts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String()),
        sa.Column("key_label", sa.String(128), nullable=False),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("status_code", sa.Integer()),
        sa.Column("failure_reason", sa.String(80)),
        sa.Column("downstream_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        if_not_exists=True,
    )
    op.create_index("ix_swissai_attempts_request", "swissai_attempts", ["request_id"], if_not_exists=True)
    op.create_index("ix_swissai_attempts_started", "swissai_attempts", ["started_at"], if_not_exists=True)
    op.create_table(
        "swissai_continuations",
        sa.Column("id", sa.String(512), primary_key=True),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        if_not_exists=True,
    )
    op.create_index("ix_swissai_continuations_created", "swissai_continuations", ["created_at"], if_not_exists=True)
    op.create_table(
        "swissai_runtime",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        if_not_exists=True,
    )


def downgrade() -> None:
    for table in (
        "swissai_runtime",
        "swissai_continuations",
        "swissai_attempts",
        "swissai_leases",
        "swissai_key_state",
    ):
        op.drop_table(table)
