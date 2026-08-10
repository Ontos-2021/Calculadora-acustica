"""Add stored asset metadata.

Revision ID: 0001_stored_assets
Revises: None
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_stored_assets"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if "stored_assets" in sa.inspect(connection).get_table_names():
        return
    op.create_table(
        "stored_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("license_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["license_id"], ["licenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_stored_assets_license_id", "stored_assets", ["license_id"])
    op.create_index("ix_stored_assets_user_id", "stored_assets", ["user_id"])
    op.create_index("ix_stored_assets_storage_key", "stored_assets", ["storage_key"])
    op.create_index("ix_stored_assets_sha256", "stored_assets", ["sha256"])
    op.create_index("ix_stored_assets_status", "stored_assets", ["status"])
    op.create_index("ix_stored_assets_created_at", "stored_assets", ["created_at"])
    op.create_index("ix_stored_assets_license_status", "stored_assets", ["license_id", "status"])
    op.create_index("ix_stored_assets_user_created", "stored_assets", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("stored_assets")
