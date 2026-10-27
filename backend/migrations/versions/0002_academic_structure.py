"""Add faculty-owned academic structure and student enrollment."""

from alembic import op

import app.models
from app.database import Base

revision = "0002_academic_structure"
down_revision = "0001_auth_accounts"
branch_labels = None
depends_on = None


ACADEMIC_STRUCTURE_TABLES = (
    "academic_years",
    "departments",
    "branches",
    "semesters",
    "class_sections",
    "faculty_section_assignments",
    "subjects",
    "student_enrollments",
)


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in ACADEMIC_STRUCTURE_TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Preserve academic records during downgrade; destructive removal is explicit.
    pass
