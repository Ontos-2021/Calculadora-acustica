"""Add object categories and project attachments.

Revision ID: 0003_projects_assets
Revises: 0002_job_artifacts
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_projects_assets"
down_revision = "0002_job_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("stored_assets")}
    if "category" not in columns:
        with op.batch_alter_table("stored_assets") as batch:
            batch.add_column(
                sa.Column("category", sa.String(length=32), nullable=False, server_default="upload")
            )
            batch.create_index("ix_stored_assets_category", ["category"])
    if "project_assets" not in inspector.get_table_names():
        op.create_table(
            "project_assets",
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("asset_id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["stored_assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("project_id", "asset_id"),
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "project_assets" in inspector.get_table_names():
        op.drop_table("project_assets")
    columns = {column["name"] for column in inspector.get_columns("stored_assets")}
    if "category" in columns:
        with op.batch_alter_table("stored_assets") as batch:
            batch.drop_index("ix_stored_assets_category")
            batch.drop_column("category")
