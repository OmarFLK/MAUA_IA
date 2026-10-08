"""Create the production application schema.

Revision ID: 20261008_0001
Revises:
Create Date: 2026-10-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261008_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tables = _tables()
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("email", sa.String(320), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("role", sa.String(20), server_default="user", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    else:
        columns = _columns("users")
        if "role" not in columns:
            op.add_column("users", sa.Column("role", sa.String(20), server_default="user", nullable=False))
        if "updated_at" not in columns:
            updated_default = (
                sa.text("'1970-01-01 00:00:00'")
                if op.get_bind().dialect.name == "sqlite"
                else sa.func.now()
            )
            op.add_column(
                "users",
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    server_default=updated_default,
                    nullable=False,
                ),
            )
            op.execute(sa.text("UPDATE users SET updated_at = created_at"))
        if "last_login_at" not in columns:
            op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    tables = _tables()
    if "conversations" not in tables:
        op.create_table(
            "conversations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("public_id", sa.String(100), nullable=False),
            sa.Column("title", sa.String(80), server_default="Nova conversa", nullable=False),
            sa.Column("assistant_mode", sa.String(20), server_default="cmob", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("assistant_mode IN ('cmob', 'general')", name="ck_conversations_assistant_mode"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "public_id", name="uq_conversations_user_public_id"),
        )
        op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"])

    if "conversation_messages" not in tables:
        op.create_table(
            "conversation_messages",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("conversation_id", sa.Uuid(), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("reasoning", sa.Text(), nullable=True),
            sa.Column("feedback", sa.String(20), nullable=True),
            sa.Column("usage", sa.JSON(), nullable=True),
            sa.Column("duration_ms", sa.Float(), nullable=True),
            sa.Column("ttft_ms", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_messages_conversation_created",
            "conversation_messages",
            ["conversation_id", "created_at"],
        )
        op.create_index("ix_messages_expires_at", "conversation_messages", ["expires_at"])

    if "conversation_states" not in tables:
        op.create_table(
            "conversation_states",
            sa.Column("conversation_id", sa.Uuid(), nullable=False),
            sa.Column("state_json", sa.JSON(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("conversation_id"),
        )

    if "user_preferences" not in tables:
        op.create_table(
            "user_preferences",
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("key", sa.String(80), nullable=False),
            sa.Column("value", sa.JSON(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "key"),
        )


def downgrade() -> None:
    tables = _tables()
    for table in ("user_preferences", "conversation_states", "conversation_messages", "conversations"):
        if table in tables:
            op.drop_table(table)

    if "users" in tables:
        columns = _columns("users")
        for column in ("last_login_at", "updated_at", "role"):
            if column in columns:
                with op.batch_alter_table("users") as batch_op:
                    batch_op.drop_column(column)
