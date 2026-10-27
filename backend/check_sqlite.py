import sqlite3
from pathlib import Path


TABLES = (
    "students",
    "user_accounts",
    "auth_sessions",
    "academic_years",
    "departments",
    "branches",
    "semesters",
    "subjects",
    "student_enrollments",
)

DATABASE_PATH = Path(__file__).resolve().with_name("edupilot.db")


def main() -> None:
    database_uri = f"{DATABASE_PATH.as_uri()}?mode=ro"
    connection = sqlite3.connect(database_uri, uri=True)
    try:
        for table in TABLES:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if exists is None:
                print(f"{table}: table not found")
                continue

            count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            print(f"{table}: {count}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
