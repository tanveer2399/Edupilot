import os
import sys
import psycopg

url = os.environ.get("NEON_DATABASE_URL")
if not url:
    sys.exit("STOP: NEON_DATABASE_URL is not set.")

tables = [
    "students", "user_accounts", "student_accounts",
    "faculty_accounts", "academic_years", "departments",
    "branches", "semesters", "class_sections", "subjects",
    "faculty_section_assignments", "student_enrollments",
    "assignments", "attendance_records", "mark_records",
    "timetable_entries",
]

try:
    with psycopg.connect(url, connect_timeout=10) as conn:
        conn.execute("SET default_transaction_read_only = on")
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")

                cur.execute("""
                    SELECT version_num
                    FROM public.alembic_version
                """)
                print("Migration revision:", cur.fetchall())

                for table in tables:
                    cur.execute(
                        f'SELECT COUNT(*) FROM public."{table}"'
                    )
                    print(f"{table}: {cur.fetchone()[0]}")

except Exception as exc:
    # Avoid printing exception details that could contain connection info.
    print("Inspection failed. Error type:", type(exc).__name__)
    sys.exit(1)
