"""Add role-backed accounts and sessions without deleting legacy records."""

from alembic import op
import sqlalchemy as sa

import app.models
from app.database import Base

revision = "0001_auth_accounts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)

    inspector = sa.inspect(bind)
    student_columns = {column["name"] for column in inspector.get_columns("students")}
    if "is_demo" not in student_columns:
        op.add_column(
            "students",
            sa.Column("is_demo", sa.Boolean(), nullable=True),
        )
        op.execute(sa.text("UPDATE students SET is_demo = false"))
        with op.batch_alter_table("students") as batch:
            batch.alter_column(
                "is_demo",
                existing_type=sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )


def downgrade() -> None:
    # Authentication records and the demo marker must not be dropped implicitly.
    pass
