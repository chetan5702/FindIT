"""Verified institutional identities and one-use recovery tokens.

Revision ID: b94e13d052c8
Revises: a83d02c941b7
"""
from alembic import op
import sqlalchemy as sa
revision = "b94e13d052c8"
down_revision = "a83d02c941b7"
branch_labels = None
depends_on = None


def upgrade():
    # Existing accounts must prove their mailbox; do not silently grandfather them.
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_table("auth_action_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(32), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "purpose", name="uq_auth_action_user_purpose"),
        sa.CheckConstraint("purpose IN ('verify','reset')", name="ck_auth_action_purpose"))
    op.create_index("ix_auth_action_tokens_user_id", "auth_action_tokens", ["user_id"])
    op.create_index("ix_auth_action_tokens_expires_at", "auth_action_tokens", ["expires_at"])
    op.execute(sa.text("DELETE FROM auth_sessions"))


def downgrade():
    op.drop_table("auth_action_tokens")
    op.drop_column("users", "email_verified")
