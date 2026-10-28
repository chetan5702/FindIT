"""Shared authentication request limits.

Revision ID: a83d02c941b7
Revises: f312b10f7098
"""
from alembic import op
import sqlalchemy as sa
revision = "a83d02c941b7"
down_revision = "f312b10f7098"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("auth_rate_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False))
    op.create_index("ix_auth_rate_buckets_window_start", "auth_rate_buckets", ["window_start"])


def downgrade():
    op.drop_table("auth_rate_buckets")
