import argparse
import os
import sqlite3
import sys
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text
from sqlalchemy.engine import Connection, Engine, URL, make_url


EXPECTED_REVISION = "0003_student_password_setup"
DATABASE_PATH = Path(__file__).resolve().with_name("edupilot.db")

TABLE_COLUMNS = {
    "students": (
        "student_id", "full_name", "email", "department", "semester", "is_demo",
    ),
    "user_accounts": (
        "id", "email", "password_hash", "role", "is_active",
        "password_setup_required", "created_at", "updated_at",
    ),
    "student_accounts": ("user_id", "student_id"),
    "faculty_accounts": ("user_id", "faculty_code", "full_name"),
    "academic_years": (
        "id", "name", "start_date", "end_date", "created_by_user_id", "created_at",
    ),
    "departments": ("id", "code", "name", "created_by_user_id", "created_at"),
    "branches": (
        "id", "department_id", "code", "name", "created_by_user_id", "created_at",
    ),
    "semesters": (
        "id", "academic_year_id", "number", "name", "start_date", "end_date",
        "created_by_user_id", "created_at",
    ),
    "class_sections": (
        "id", "branch_id", "academic_year_id", "semester_id", "name",
        "created_by_user_id", "created_at",
    ),
    "faculty_section_assignments": (
        "faculty_user_id", "section_id", "assigned_at",
    ),
    "subjects": (
        "id", "branch_id", "semester_id", "code", "name", "credits",
        "created_by_user_id", "created_at",
    ),
    "student_enrollments": (
        "id", "student_id", "section_id", "semester_id", "status", "enrolled_at",
    ),
    "assignments": (
        "id", "student_id", "subject", "title", "description", "due_date", "status",
    ),
    "attendance_records": (
        "id", "student_id", "subject", "class_date", "status", "remarks",
    ),
    "mark_records": (
        "id", "student_id", "subject", "assessment_name", "marks_obtained",
        "maximum_marks", "assessment_date",
    ),
    "timetable_entries": (
        "id", "student_id", "subject", "day_of_week", "start_time", "end_time",
        "location",
    ),
    "auth_sessions": (
        "id", "user_id", "token_hash", "expires_at", "revoked_at", "created_at",
    ),
    "student_password_setup_tokens": (
        "id", "user_id", "token_hash", "expires_at", "used_at", "created_at",
    ),
}

TRANSFER_ORDER = (
    "students",
    "user_accounts",
    "student_accounts",
    "faculty_accounts",
    "academic_years",
    "departments",
    "branches",
    "semesters",
    "class_sections",
    "subjects",
    "faculty_section_assignments",
    "student_enrollments",
    "assignments",
    "attendance_records",
    "mark_records",
    "timetable_entries",
)

PRIMARY_KEYS = {
    "students": ("student_id",),
    "user_accounts": ("id",),
    "student_accounts": ("user_id",),
    "faculty_accounts": ("user_id",),
    "academic_years": ("id",),
    "departments": ("id",),
    "branches": ("id",),
    "semesters": ("id",),
    "class_sections": ("id",),
    "faculty_section_assignments": ("faculty_user_id", "section_id"),
    "subjects": ("id",),
    "student_enrollments": ("id",),
    "assignments": ("id",),
    "attendance_records": ("id",),
    "mark_records": ("id",),
    "timetable_entries": ("id",),
    "auth_sessions": ("id",),
    "student_password_setup_tokens": ("id",),
}

UNIQUE_KEYS = {
    "students": (("email",),),
    "user_accounts": (("email",), ("email_lower",)),
    "student_accounts": (("student_id",),),
    "faculty_accounts": (("faculty_code",),),
    "academic_years": (("name",),),
    "departments": (("code",),),
    "branches": (("department_id", "code"),),
    "semesters": (("academic_year_id", "number"),),
    "class_sections": (
        ("branch_id", "academic_year_id", "semester_id", "name"),
    ),
    "subjects": (("branch_id", "semester_id", "code"),),
    "student_enrollments": (("student_id", "semester_id"),),
    "attendance_records": (("student_id", "subject", "class_date"),),
}

FOREIGN_KEYS = (
    ("student_accounts", "user_id", "user_accounts", "id"),
    ("student_accounts", "student_id", "students", "student_id"),
    ("faculty_accounts", "user_id", "user_accounts", "id"),
    ("auth_sessions", "user_id", "user_accounts", "id"),
    ("student_password_setup_tokens", "user_id", "user_accounts", "id"),
    ("academic_years", "created_by_user_id", "user_accounts", "id"),
    ("departments", "created_by_user_id", "user_accounts", "id"),
    ("branches", "department_id", "departments", "id"),
    ("branches", "created_by_user_id", "user_accounts", "id"),
    ("semesters", "academic_year_id", "academic_years", "id"),
    ("semesters", "created_by_user_id", "user_accounts", "id"),
    ("class_sections", "branch_id", "branches", "id"),
    ("class_sections", "academic_year_id", "academic_years", "id"),
    ("class_sections", "semester_id", "semesters", "id"),
    ("class_sections", "created_by_user_id", "user_accounts", "id"),
    ("faculty_section_assignments", "faculty_user_id", "user_accounts", "id"),
    ("faculty_section_assignments", "section_id", "class_sections", "id"),
    ("subjects", "branch_id", "branches", "id"),
    ("subjects", "semester_id", "semesters", "id"),
    ("subjects", "created_by_user_id", "user_accounts", "id"),
    ("student_enrollments", "student_id", "students", "student_id"),
    ("student_enrollments", "section_id", "class_sections", "id"),
    ("student_enrollments", "semester_id", "semesters", "id"),
    ("assignments", "student_id", "students", "student_id"),
    ("attendance_records", "student_id", "students", "student_id"),
    ("mark_records", "student_id", "students", "student_id"),
    ("timetable_entries", "student_id", "students", "student_id"),
)

BOOLEAN_COLUMNS = {
    ("students", "is_demo"),
    ("user_accounts", "is_active"),
    ("user_accounts", "password_setup_required"),
}
DATE_COLUMNS = {
    ("academic_years", "start_date"),
    ("academic_years", "end_date"),
    ("semesters", "start_date"),
    ("semesters", "end_date"),
    ("assignments", "due_date"),
    ("attendance_records", "class_date"),
    ("mark_records", "assessment_date"),
}
TIME_COLUMNS = {
    ("timetable_entries", "start_time"),
    ("timetable_entries", "end_time"),
}
DATETIME_COLUMNS = {
    ("user_accounts", "created_at"),
    ("user_accounts", "updated_at"),
    ("academic_years", "created_at"),
    ("departments", "created_at"),
    ("branches", "created_at"),
    ("semesters", "created_at"),
    ("class_sections", "created_at"),
    ("faculty_section_assignments", "assigned_at"),
    ("student_enrollments", "enrolled_at"),
    ("subjects", "created_at"),
    ("auth_sessions", "expires_at"),
    ("auth_sessions", "revoked_at"),
    ("auth_sessions", "created_at"),
    ("student_password_setup_tokens", "expires_at"),
    ("student_password_setup_tokens", "used_at"),
    ("student_password_setup_tokens", "created_at"),
}
DECIMAL_COLUMNS = {("subjects", "credits")}
FLOAT_COLUMNS = {
    ("mark_records", "marks_obtained"),
    ("mark_records", "maximum_marks"),
}

INTEGER_COLUMNS = {
    ("students", "semester"),
    ("academic_years", "id"),
    ("departments", "id"),
    ("branches", "id"),
    ("semesters", "id"),
    ("semesters", "number"),
    ("class_sections", "id"),
    ("faculty_section_assignments", "section_id"),
    ("subjects", "id"),
    ("student_enrollments", "id"),
    ("student_enrollments", "section_id"),
    ("student_enrollments", "semester_id"),
    ("assignments", "id"),
    ("attendance_records", "id"),
    ("mark_records", "id"),
    ("timetable_entries", "id"),
}

INTEGER_ID_TABLES = (
    "academic_years",
    "departments",
    "branches",
    "semesters",
    "class_sections",
    "subjects",
    "student_enrollments",
    "assignments",
    "attendance_records",
    "mark_records",
    "timetable_entries",
)


class MigrationSafetyError(Exception):
    pass


def quote_identifier(engine: Engine, identifier: str) -> str:
    return engine.dialect.identifier_preparer.quote_identifier(identifier)


def normalize_value(table: str, column: str, value: Any) -> Any:
    key = (table, column)
    if value is None:
        return None
    if key in BOOLEAN_COLUMNS:
        if value is True or value == 1:
            return True
        if value is False or value == 0:
            return False
        raise MigrationSafetyError(f"Invalid Boolean value in {table}.{column}.")
    if key in DATE_COLUMNS:
        if isinstance(value, datetime):
            raise MigrationSafetyError(f"Invalid date value in {table}.{column}.")
        try:
            return value if isinstance(value, date) else date.fromisoformat(str(value))
        except ValueError as exc:
            raise MigrationSafetyError(
                f"Invalid date value in {table}.{column}."
            ) from exc
    if key in TIME_COLUMNS:
        try:
            return value if isinstance(value, time) else time.fromisoformat(str(value))
        except ValueError as exc:
            raise MigrationSafetyError(
                f"Invalid time value in {table}.{column}."
            ) from exc
    if key in DATETIME_COLUMNS:
        try:
            parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise MigrationSafetyError(
                f"Invalid timestamp in {table}.{column}."
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    if key in DECIMAL_COLUMNS:
        try:
            parsed_decimal = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise MigrationSafetyError(
                f"Invalid value for {table}.{column}: {value!r}."
            ) from exc
        if not parsed_decimal.is_finite():
            raise MigrationSafetyError(
                f"Invalid value for {table}.{column}: {value!r}."
            )
        try:
            one_decimal_place = parsed_decimal.quantize(Decimal("0.1"))
        except InvalidOperation as exc:
            raise MigrationSafetyError(
                f"Value for {table}.{column} is outside NUMERIC(4,1) precision: "
                f"{value!r}."
            ) from exc
        if parsed_decimal != one_decimal_place:
            raise MigrationSafetyError(
                f"Value for {table}.{column} is not representable at one decimal "
                f"place: {value!r}."
            )
        if one_decimal_place < Decimal("-999.9") or one_decimal_place > Decimal("999.9"):
            raise MigrationSafetyError(
                f"Value for {table}.{column} is outside NUMERIC(4,1) range "
                f"[-999.9, 999.9]: {value!r}."
            )
        return one_decimal_place
    if key in FLOAT_COLUMNS:
        try:
            parsed_float = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MigrationSafetyError(
                f"Invalid numeric value in {table}.{column}."
            ) from exc
        if parsed_float != parsed_float or abs(parsed_float) == float("inf"):
            raise MigrationSafetyError(f"Invalid numeric value in {table}.{column}.")
        return parsed_float
    if key in INTEGER_COLUMNS:
        if isinstance(value, bool):
            raise MigrationSafetyError(f"Invalid integer in {table}.{column}.")
        try:
            parsed_integer = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MigrationSafetyError(
                f"Invalid integer in {table}.{column}."
            ) from exc
        if parsed_integer != value:
            raise MigrationSafetyError(f"Invalid integer in {table}.{column}.")
        return parsed_integer
    return str(value)


def read_source_rows(source: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for table in TRANSFER_ORDER:
        columns = TABLE_COLUMNS[table]
        selected = ", ".join(f'"{column}"' for column in columns)
        rows = source.execute(f'SELECT {selected} FROM "{table}"').fetchall()
        result[table] = [
            {
                column: normalize_value(table, column, value)
                for column, value in zip(columns, row)
            }
            for row in rows
        ]
    return result


def validate_source(source: sqlite3.Connection) -> None:
    revision_rows = source.execute(
        'SELECT version_num FROM "alembic_version"'
    ).fetchall()
    if [row[0] for row in revision_rows] != [EXPECTED_REVISION]:
        raise MigrationSafetyError("SQLite is not at the expected Alembic revision.")

    tables = {
        row[0]
        for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    expected_tables = set(TABLE_COLUMNS) | {"alembic_version"}
    if not expected_tables.issubset(tables):
        raise MigrationSafetyError("SQLite is missing one or more expected tables.")

    for table, expected_columns in TABLE_COLUMNS.items():
        actual_columns = tuple(
            row[1] for row in source.execute(f'PRAGMA table_info("{table}")')
        )
        if set(actual_columns) != set(expected_columns):
            raise MigrationSafetyError(
                f"SQLite columns do not match the expected schema for {table}."
            )
        table_info = source.execute(f'PRAGMA table_info("{table}")').fetchall()
        actual_primary_key = tuple(
            row[1]
            for row in sorted(
                (row for row in table_info if row[5] > 0),
                key=lambda row: row[5],
            )
        )
        if actual_primary_key != PRIMARY_KEYS[table]:
            raise MigrationSafetyError(
                f"SQLite primary key does not match the expected schema for {table}."
            )

    foreign_key_violations = source.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_violations:
        raise MigrationSafetyError(
            f"SQLite has {len(foreign_key_violations)} foreign-key violations."
        )

    for child, child_column, parent, parent_column in FOREIGN_KEYS:
        actual = {
            (row[2], row[3], row[4])
            for row in source.execute(f'PRAGMA foreign_key_list("{child}")')
        }
        if (parent, child_column, parent_column) not in actual:
            raise MigrationSafetyError(
                f"SQLite foreign-key schema does not match for {child}."
            )


def validate_target_schema(connection: Connection) -> dict[str, Table]:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names(schema="public"))
    expected_tables = set(TABLE_COLUMNS) | {"alembic_version"}
    if not expected_tables.issubset(tables):
        raise MigrationSafetyError("Neon is missing one or more expected tables.")

    revision_rows = connection.execute(
        text('SELECT version_num FROM public.alembic_version')
    ).fetchall()
    if [row[0] for row in revision_rows] != [EXPECTED_REVISION]:
        raise MigrationSafetyError("Neon is not at the expected Alembic revision.")

    metadata = MetaData()
    reflected: dict[str, Table] = {}
    for table, expected_columns in TABLE_COLUMNS.items():
        actual_columns = tuple(
            column["name"] for column in inspector.get_columns(table, schema="public")
        )
        if set(actual_columns) != set(expected_columns):
            raise MigrationSafetyError(
                f"Neon columns do not match the expected schema for {table}."
            )
        reflected[table] = Table(
            table, metadata, schema="public", autoload_with=connection
        )
        actual_primary_key = tuple(
            inspector.get_pk_constraint(table, schema="public")[
                "constrained_columns"
            ]
            or ()
        )
        if actual_primary_key != PRIMARY_KEYS[table]:
            raise MigrationSafetyError(
                f"Neon primary key does not match the expected schema for {table}."
            )

    for child, child_column, parent, parent_column in FOREIGN_KEYS:
        constraints = inspector.get_foreign_keys(child, schema="public")
        if not any(
            constraint.get("referred_table") == parent
            and constraint.get("constrained_columns") == [child_column]
            and constraint.get("referred_columns") == [parent_column]
            and (constraint.get("referred_schema") in (None, "public"))
            for constraint in constraints
        ):
            raise MigrationSafetyError(
                f"Neon foreign-key schema does not match for {child}."
            )
    return reflected


def row_key(row: dict[str, Any], columns: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row[column] for column in columns)


def unique_key(row: dict[str, Any], columns: tuple[str, ...]) -> tuple[Any, ...]:
    if columns == ("email_lower",):
        email = row["email"]
        return (email.lower() if email is not None else None,)
    return row_key(row, columns)


def analyze_tables(
    source_rows: dict[str, list[dict[str, Any]]],
    target_rows: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int], dict[str, int]]:
    pending: dict[str, list[dict[str, Any]]] = {}
    skipped: dict[str, int] = {}
    conflicts: dict[str, int] = {}

    for table in TRANSFER_ORDER:
        source = source_rows[table]
        target = target_rows[table]
        primary_key = PRIMARY_KEYS[table]
        source_by_key = {row_key(row, primary_key): row for row in source}
        target_by_key = {row_key(row, primary_key): row for row in target}
        source_conflicts: set[tuple[Any, ...]] = set()
        target_conflicts: set[tuple[Any, ...]] = set()
        matching_keys: set[tuple[Any, ...]] = set()

        if len(source_by_key) != len(source):
            conflicts[table] = len(source)
            skipped[table] = 0
            pending[table] = []
            continue

        for row in source:
            key = row_key(row, primary_key)
            existing = target_by_key.get(key)
            if existing is not None:
                if existing == row:
                    matching_keys.add(key)
                else:
                    source_conflicts.add(key)
                    target_conflicts.add(key)

        for unique_columns in UNIQUE_KEYS.get(table, ()):
            source_unique: dict[tuple[Any, ...], tuple[Any, ...]] = {}
            target_unique: dict[tuple[Any, ...], tuple[Any, ...]] = {}
            for row in source:
                value = unique_key(row, unique_columns)
                key = row_key(row, primary_key)
                previous = source_unique.get(value)
                if previous is not None and previous != key:
                    source_conflicts.update((previous, key))
                else:
                    source_unique[value] = key
            for row in target:
                target_unique[unique_key(row, unique_columns)] = row_key(
                    row, primary_key
                )
            for row in source:
                key = row_key(row, primary_key)
                conflicting_target_key = target_unique.get(
                    unique_key(row, unique_columns)
                )
                if (
                    conflicting_target_key is not None
                    and conflicting_target_key != key
                ):
                    source_conflicts.add(key)
                    target_conflicts.add(conflicting_target_key)

        for key in target_by_key:
            if key not in source_by_key:
                target_conflicts.add(key)

        pending[table] = [
            row
            for row in source
            if row_key(row, primary_key) not in matching_keys
            and row_key(row, primary_key) not in source_conflicts
        ]
        skipped[table] = len(matching_keys)
        conflicts[table] = len(source_conflicts | target_conflicts)
    return pending, skipped, conflicts


def read_target_rows(
    connection: Connection, tables: dict[str, Table]
) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for table_name in TRANSFER_ORDER:
        table = tables[table_name]
        result[table_name] = [
            {
                column: normalize_value(table_name, column, value)
                for column, value in row.items()
            }
            for row in connection.execute(select(table)).mappings()
        ]
    return result


def count_foreign_key_violations(
    connection: Connection, tables: dict[str, Table]
) -> int:
    total = 0
    for child_name, child_column, parent_name, parent_column in FOREIGN_KEYS:
        child = tables[child_name]
        parent = tables[parent_name]
        orphan_count = connection.execute(
            select(func.count())
            .select_from(
                child.outerjoin(
                    parent,
                    child.c[child_column] == parent.c[parent_column],
                )
            )
            .where(
                child.c[child_column].is_not(None),
                parent.c[parent_column].is_(None),
            )
        ).scalar_one()
        total += orphan_count
    return total


def reset_sequences(connection: Connection, engine: Engine) -> None:
    for table_name in INTEGER_ID_TABLES:
        sequence = connection.execute(
            text(
                "SELECT n.nspname, c.relname "
                "FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.oid = pg_get_serial_sequence(:table_name, 'id')::regclass"
            ),
            {"table_name": f"public.{table_name}"},
        ).one_or_none()
        if sequence is None:
            raise MigrationSafetyError(
                f"Neon integer ID sequence is missing for {table_name}."
            )
        maximum = connection.execute(
            text(f'SELECT MAX("id") FROM public.{quote_identifier(engine, table_name)}')
        ).scalar_one()
        next_value = 1 if maximum is None else int(maximum) + 1
        qualified_sequence = (
            f"{quote_identifier(engine, sequence[0])}."
            f"{quote_identifier(engine, sequence[1])}"
        )
        connection.execute(
            text(f"ALTER SEQUENCE {qualified_sequence} RESTART WITH {next_value}")
        )


def verify_transfer(
    connection: Connection,
    tables: dict[str, Table],
    source_rows: dict[str, list[dict[str, Any]]],
) -> None:
    target_rows = read_target_rows(connection, tables)
    for table in TRANSFER_ORDER:
        source_by_key = {
            row_key(row, PRIMARY_KEYS[table]): row for row in source_rows[table]
        }
        target_by_key = {
            row_key(row, PRIMARY_KEYS[table]): row for row in target_rows[table]
        }
        if source_by_key != target_by_key:
            raise MigrationSafetyError(
                f"Post-insert record verification failed for {table}."
            )
    if count_foreign_key_violations(connection, tables):
        raise MigrationSafetyError("Neon foreign-key integrity verification failed.")


def print_report(
    source_rows: dict[str, list[dict[str, Any]]],
    skipped: dict[str, int],
    conflicts: dict[str, int],
    inserted: dict[str, int],
    attempted: dict[str, int] | None = None,
    rolled_back: bool = False,
) -> None:
    headers = ["table", "source", "inserted", "skipped", "conflicting"]
    if attempted is not None:
        headers.append("attempted")
    if rolled_back:
        headers.append("committed")
    print(" | ".join(headers))
    for table in TRANSFER_ORDER:
        values = [
            table,
            str(len(source_rows[table])),
            str(inserted.get(table, 0)),
            str(skipped.get(table, 0)),
            str(conflicts.get(table, 0)),
        ]
        if attempted is not None:
            values.append(str(attempted.get(table, 0)))
        if rolled_back:
            values.append("0")
        print(" | ".join(values))


def validate_neon_url(raw_url: str | None) -> URL:
    if not raw_url:
        raise MigrationSafetyError("NEON_DATABASE_URL is required.")
    try:
        url = make_url(raw_url)
    except Exception as exc:
        raise MigrationSafetyError("NEON_DATABASE_URL is invalid.") from exc
    if url.drivername not in ("postgresql", "postgres", "postgresql+psycopg"):
        raise MigrationSafetyError("NEON_DATABASE_URL must use PostgreSQL.")
    if not url.host or not url.host.lower().endswith(".neon.tech"):
        raise MigrationSafetyError(
            "NEON_DATABASE_URL must identify a Neon PostgreSQL host."
        )
    return url.set(drivername="postgresql+psycopg")


def run(apply_changes: bool) -> int:
    source_uri = f"{DATABASE_PATH.as_uri()}?mode=ro"
    try:
        source = sqlite3.connect(source_uri, uri=True)
    except sqlite3.Error as exc:
        raise MigrationSafetyError("Could not open the SQLite source read-only.") from exc

    engine: Engine | None = None
    try:
        source.execute("BEGIN")
        validate_source(source)
        source_rows = read_source_rows(source)
        target_url = validate_neon_url(os.environ.get("NEON_DATABASE_URL"))
        engine = create_engine(
            target_url,
            pool_pre_ping=True,
            hide_parameters=True,
        )

        with engine.connect() as connection:
            transaction = connection.begin()
            attempted: dict[str, int] = {table: 0 for table in TRANSFER_ORDER}
            try:
                connection.execute(
                    text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                )
                reflected_tables = validate_target_schema(connection)
                if count_foreign_key_violations(connection, reflected_tables):
                    raise MigrationSafetyError(
                        "Neon has existing foreign-key integrity violations."
                    )

                target_rows = read_target_rows(connection, reflected_tables)
                pending, skipped, conflicts = analyze_tables(
                    source_rows, target_rows
                )
                print_report(
                    source_rows,
                    skipped,
                    conflicts,
                    {table: 0 for table in TRANSFER_ORDER},
                )
                if any(conflicts.values()):
                    transaction.rollback()
                    print(
                        "Stopped before writing: destination data is not an exact, "
                        "conflict-free subset of the SQLite source."
                    )
                    return 1

                planned = {table: len(pending[table]) for table in TRANSFER_ORDER}
                if not apply_changes:
                    transaction.rollback()
                    print(
                        "Dry run only; no records were written. "
                        f"Rows eligible to insert: {sum(planned.values())}."
                    )
                    return 0

                print(
                    "WARNING: --apply will write application records to the Neon "
                    "database in one transaction. SQLite remains read-only."
                )
                for table_name in TRANSFER_ORDER:
                    rows = pending[table_name]
                    attempted[table_name] = len(rows)
                    if rows:
                        connection.execute(
                            reflected_tables[table_name].insert(),
                            rows,
                        )

                reset_sequences(connection, engine)
                verify_transfer(connection, reflected_tables, source_rows)
                transaction.commit()
                print_report(
                    source_rows,
                    skipped,
                    conflicts,
                    planned,
                    attempted=attempted,
                )
                print(
                    f"Transfer committed. Inserted {sum(planned.values())}; "
                    f"skipped {sum(skipped.values())} identical records."
                )
                return 0
            except Exception:
                rollback_confirmed = False
                rollback_error: Exception | None = None
                if transaction.is_active:
                    try:
                        transaction.rollback()
                    except Exception as exc:
                        rollback_error = exc
                    else:
                        rollback_confirmed = True
                print_report(
                    source_rows,
                    locals().get("skipped", {table: 0 for table in TRANSFER_ORDER}),
                    locals().get("conflicts", {table: 0 for table in TRANSFER_ORDER}),
                    {table: 0 for table in TRANSFER_ORDER},
                    attempted=attempted,
                    rolled_back=rollback_confirmed,
                )
                if rollback_confirmed:
                    print("PostgreSQL transaction rollback confirmed.")
                else:
                    print(
                        "PostgreSQL transaction rollback NOT CONFIRMED; "
                        "Neon state is uncertain.",
                        file=sys.stderr,
                    )
                if rollback_error is not None:
                    raise MigrationSafetyError(
                        "Migration failed and PostgreSQL rollback failed; "
                        "Neon state is uncertain."
                    ) from rollback_error
                raise
    finally:
        source.close()
        if engine is not None:
            engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely transfer application records from SQLite to Neon."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write records after all preflight checks pass (default: dry run)",
    )
    args = parser.parse_args()
    try:
        return run(args.apply)
    except MigrationSafetyError as exc:
        print(f"Stopped safely: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Database exceptions can include connection details; never print them.
        print(
            f"Migration failed ({type(exc).__name__}); no credentials or row data "
            "were displayed.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
