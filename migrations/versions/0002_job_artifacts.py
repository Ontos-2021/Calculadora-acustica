"""Associate stored assets with jobs.

Revision ID: 0002_job_artifacts
Revises: 0001_stored_assets
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_job_artifacts"
down_revision = "0001_stored_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stored_assets") as batch:
        batch.add_column(sa.Column("job_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_stored_assets_job_id", "jobs", ["job_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_stored_assets_job_id", ["job_id"])


def downgrade() -> None:
    with op.batch_alter_table("stored_assets") as batch:
        batch.drop_index("ix_stored_assets_job_id")
        batch.drop_constraint("fk_stored_assets_job_id", type_="foreignkey")
        batch.drop_column("job_id")
