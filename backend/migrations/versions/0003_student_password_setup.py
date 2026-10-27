"""Add expiring student password setup tokens."""

from alembic import op
import sqlalchemy as sa

revision = "0003_student_password_setup"
down_revision = "0002_academic_structure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("user_accounts")}
    if "password_setup_required" not in user_columns:
        op.add_column(
            "user_accounts",
            sa.Column(
                "password_setup_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if not inspector.has_table("student_password_setup_tokens"):
        op.create_table(
            "student_password_setup_tokens",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(length=36),
                sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
        )
        op.create_index(
            "ix_student_password_setup_tokens_expires_at",
            "student_password_setup_tokens",
            ["expires_at"],
        )
    if bind.dialect.name == "sqlite":
        has_email_index = bind.execute(
            sa.text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'index' "
                "AND name = 'uq_user_accounts_email_case_insensitive'"
            )
        ).scalar_one_or_none() is not None
    else:
        has_email_index = any(
            index["name"] == "uq_user_accounts_email_case_insensitive"
            for index in sa.inspect(bind).get_indexes("user_accounts")
        )
    if not has_email_index:
        op.create_index(
            "uq_user_accounts_email_case_insensitive",
            "user_accounts",
            [sa.text("lower(email)")],
            unique=True,
        )


def downgrade() -> None:
    # Keep student account state and tokens during downgrade to avoid data loss.
    pass
