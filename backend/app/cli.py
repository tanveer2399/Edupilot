import getpass
from uuid import uuid4

from alembic import command
from alembic.config import Config
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.core.config import BACKEND_DIR
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.auth import FacultyAccount, UserAccount
from app.services.dev_academic_seed_service import seed_test_student_academics


def create_initial_faculty() -> None:
    migration_config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(migration_config, "head")

    with SessionLocal() as db:
        faculty_count = db.scalar(
            select(func.count())
            .select_from(UserAccount)
            .where(UserAccount.role == "faculty")
        )
        if faculty_count:
            raise SystemExit(
                "A faculty account already exists. Create further staff accounts "
                "through the authorized management workflow."
            )

        email = TypeAdapter(EmailStr).validate_python(
            input("Faculty email: ").strip()
        ).casefold()
        full_name = input("Faculty full name: ").strip()
        faculty_code = input("Faculty code: ").strip()
        if not full_name or len(full_name) > 120:
            raise SystemExit("Faculty name must contain 1 to 120 characters.")
        if not faculty_code or len(faculty_code) > 32:
            raise SystemExit("Faculty code must contain 1 to 32 characters.")
        password = getpass.getpass("Password (at least 12 characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if len(password) < 12:
            raise SystemExit("Password must contain at least 12 characters.")
        if password != confirmation:
            raise SystemExit("Passwords did not match.")
        if db.scalar(select(UserAccount.id).where(UserAccount.email == email)):
            raise SystemExit("An account with this email already exists.")

        user = UserAccount(
            id=str(uuid4()),
            email=email,
            password_hash=hash_password(password),
            role="faculty",
        )
        user.faculty_account = FacultyAccount(
            faculty_code=faculty_code,
            full_name=full_name,
        )
        db.add(user)
        db.commit()
        print(f"Initial faculty account created for {email}.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="EduPilot local administration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "create-faculty",
        help="create the first faculty account through the local console",
    )
    seed_parser = commands.add_parser(
        "seed-test-academics",
        help="preview or seed academic records for one linked development student",
    )
    seed_parser.add_argument(
        "--student-id",
        required=True,
        help="exact student ID; no account or student is created",
    )
    seed_parser.add_argument(
        "--apply",
        action="store_true",
        help="insert missing records (default: dry run)",
    )
    arguments = parser.parse_args()
    if arguments.command == "create-faculty":
        try:
            create_initial_faculty()
        except ValidationError as error:
            raise SystemExit("Enter a valid email address.") from error
    elif arguments.command == "seed-test-academics":
        with SessionLocal() as db:
            try:
                result = seed_test_student_academics(
                    db,
                    student_id=arguments.student_id,
                    apply=arguments.apply,
                )
            except ValueError as error:
                raise SystemExit(str(error)) from error
        mode = "Dry run" if result["dry_run"] else "Applied"
        print(f"Database type: {result['database']['type']}")
        print(f"Database file: {result['database']['path']}")
        print(f"Student ID: {result['student_id']}")
        checks = result["student_checks"]
        print(
            "Eligibility: "
            f"non-demo={'yes' if checks['non_demo'] else 'no'}, "
            "active student login link="
            f"{'yes' if checks['active_student_login_link'] else 'no'}, "
            f"active enrollment={'yes' if checks['active_enrollment'] else 'no'}"
        )
        if result["dry_run"]:
            print(
                f"Dry run: {result['total_would_insert']} record(s) "
                "would be inserted."
            )
            print("Inserted: 0; skipped: " f"{result['total_skipped']}.")
        else:
            print(
                f"Applied: {result['total_inserted']} record(s) inserted; "
                f"{result['total_skipped']} skipped."
            )
        for kind, counts in result["records"].items():
            print(
                f"{kind}: would insert {counts['would_insert']}, "
                f"inserted {counts['inserted']}, skipped {counts['skipped']}."
            )
            for item in result["items"][kind]:
                key = ", ".join(
                    f"{name}={value.isoformat() if hasattr(value, 'isoformat') else value}"
                    for name, value in item["key"].items()
                )
                if result["dry_run"]:
                    label = "would insert" if item["status"] == "would_insert" else "would skip"
                else:
                    label = item["status"]
                print(f"  - {key}: {label}")
        if result["dry_run"]:
            print("Dry-run mode made no database changes.")


if __name__ == "__main__":
    main()
