"""Track multipart upload reservations.

Revision ID: 0004_multipart_uploads
Revises: 0003_projects_assets
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_multipart_uploads"
down_revision = "0003_projects_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in sa.inspect(connection).get_columns("stored_assets")}
    if "multipart_upload_id" in columns:
        return
    with op.batch_alter_table("stored_assets") as batch:
        batch.add_column(sa.Column("multipart_upload_id", sa.String(length=500), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in sa.inspect(connection).get_columns("stored_assets")}
    if "multipart_upload_id" not in columns:
        return
    with op.batch_alter_table("stored_assets") as batch:
        batch.drop_column("multipart_upload_id")
