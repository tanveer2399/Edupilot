import csv
import io
import json
from decimal import Decimal
from uuid import uuid4

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import AUTH_COOKIE_NAME
from app.models.academic_structure import (
    AcademicYear,
    Branch,
    ClassSection,
    Department,
    Semester,
    StudentEnrollment,
    Subject,
)
from app.models.auth import StudentAccount
from app.models.student import Student
from app.services import faculty_import_service


@pytest.fixture
def faculty_import_client(auth_env):
    client = auth_env["client"]
    client.cookies.set(
        AUTH_COOKIE_NAME,
        auth_env["faculty_token"],
        path="/api",
    )
    return client


def csv_file(headers, records):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(records)
    return output.getvalue().encode("utf-8")


def upload_preview(
    client,
    content,
    *,
    filename="records.csv",
    import_type="departments",
    mapping=None,
    duplicate_policy="skip",
):
    data = {
        "import_type": import_type,
        "duplicate_policy": duplicate_policy,
    }
    if mapping is not None:
        data["mapping"] = json.dumps(mapping)
    return client.post(
        "/api/faculty/imports/preview",
        files={"file": (filename, content)},
        data=data,
    )


def create_structure(client):
    year = client.post(
        "/api/faculty/academic-years",
        json={
            "name": "2026-27",
            "start_date": "2026-07-01",
            "end_date": "2027-06-30",
        },
    ).json()
    department = client.post(
        "/api/faculty/departments",
        json={"code": "CSE", "name": "Computer Science"},
    ).json()
    branch = client.post(
        "/api/faculty/branches",
        json={
            "department_id": department["id"],
            "code": "AIML",
            "name": "Artificial Intelligence",
        },
    ).json()
    semester = client.post(
        "/api/faculty/semesters",
        json={
            "academic_year_id": year["id"],
            "number": 1,
            "name": "Semester 1",
            "start_date": "2026-07-01",
            "end_date": "2026-12-31",
        },
    ).json()
    section = client.post(
        "/api/faculty/sections",
        json={
            "branch_id": branch["id"],
            "academic_year_id": year["id"],
            "semester_id": semester["id"],
            "name": "A",
        },
    ).json()
    return year, department, branch, semester, section


def commit_preview(client, preview):
    return client.post(
        "/api/faculty/imports/commit",
        json={"preview_id": preview["preview_id"], "confirm": True},
    )


def test_import_types_endpoint_and_unauthorized_access(client):
    assert client.get("/api/faculty/imports/types").status_code == 403
    assert client.post(
        "/api/faculty/imports/preview",
        files={"file": ("records.csv", b"code,name\nCSE,Computer Science")},
        data={"import_type": "departments"},
    ).status_code == 403


def test_csv_preview_maps_columns_then_commits_student_and_enrollment(
    faculty_import_client,
    auth_env,
):
    _, _, _, _, section = create_structure(faculty_import_client)
    contents = csv_file(
        [
            "College ID",
            "Name",
            "College Email",
            "Branch",
            "Academic Year",
            "Term",
            "Class",
        ],
        [["STU-IMPORT-1", "Imported Student", "imported@example.edu", "AIML", "2026-27", 1, "A"]],
    )
    initial = upload_preview(
        faculty_import_client,
        contents,
        import_type="students",
    )

    assert initial.status_code == 200
    assert initial.json()["requires_mapping"] is True
    assert initial.json()["sample_rows"][0]["row_number"] == 2
    mapping = {
        "student_id": "College ID",
        "full_name": "Name",
        "email": "College Email",
        "branch_code": "Branch",
        "academic_year": "Academic Year",
        "semester_number": "Term",
        "section_name": "Class",
    }
    preview_response = upload_preview(
        faculty_import_client,
        contents,
        import_type="students",
        mapping=mapping,
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["can_commit"] is True
    assert preview["summary"] == {
        "created": 1,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
    }
    with auth_env["session_factory"]() as db:
        assert db.get(Student, "STU-IMPORT-1") is None

    committed = commit_preview(faculty_import_client, preview)

    assert committed.status_code == 200
    assert committed.json()["summary"]["created"] == 1
    with auth_env["session_factory"]() as db:
        student = db.get(Student, "STU-IMPORT-1")
        enrollment = db.scalar(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id == "STU-IMPORT-1"
            )
        )
        assert student is not None
        assert student.email == "imported@example.edu"
        assert student.department == "Artificial Intelligence"
        assert student.is_demo is False
        assert enrollment is not None
        assert enrollment.section_id == section["id"]
        assert db.scalar(
            select(StudentAccount.user_id).where(
                StudentAccount.student_id == "STU-IMPORT-1"
            )
        ) is None


def test_xlsx_department_import_succeeds(faculty_import_client, auth_env):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Department Code", "Department Name"])
    worksheet.append(["BIO", "Biology"])
    content = io.BytesIO()
    workbook.save(content)
    response = upload_preview(
        faculty_import_client,
        content.getvalue(),
        filename="departments.xlsx",
        import_type="departments",
        mapping={"code": "Department Code", "name": "Department Name"},
    )

    assert response.status_code == 200
    assert response.json()["can_commit"] is True
    result = commit_preview(faculty_import_client, response.json())
    assert result.status_code == 200
    with auth_env["session_factory"]() as db:
        assert db.scalar(
            select(Department).where(Department.code == "BIO")
        ) is not None


@pytest.mark.parametrize(
    ("filename", "content", "expected_detail"),
    [
        ("records.xls", b"code,name\nCSE,Computer Science", "Only .csv and .xlsx"),
        ("broken.xlsx", b"not a zip workbook", "Excel file is invalid"),
        ("empty.csv", b"", "non-empty CSV or Excel"),
        ("bad.csv", b"code,name\nCSE,\"unterminated", "invalid quoting"),
    ],
)
def test_import_rejects_invalid_files(
    faculty_import_client,
    filename,
    content,
    expected_detail,
):
    response = upload_preview(faculty_import_client, content, filename=filename)

    assert response.status_code == 422
    assert expected_detail in response.json()["detail"]


def test_import_rejects_files_over_size_limit(faculty_import_client):
    response = upload_preview(
        faculty_import_client,
        b"x" * (5 * 1024 * 1024 + 1),
    )

    assert response.status_code == 422
    assert "5 MB" in response.json()["detail"]


def test_import_requires_complete_column_mapping(faculty_import_client):
    content = csv_file(["Department Code", "Department Name"], [["CSE", "Computer Science"]])
    response = upload_preview(
        faculty_import_client,
        content,
        mapping={"code": "Department Code"},
    )

    assert response.status_code == 422
    assert "Map required fields: name" in response.json()["detail"]


def test_preview_reports_row_number_for_validation_and_duplicate_errors(
    faculty_import_client,
):
    contents = csv_file(
        ["code", "name"],
        [
            ["CSE", "Computer Science"],
            ["CSE", "Duplicate row"],
            ["", "Missing code"],
        ],
    )
    response = upload_preview(
        faculty_import_client,
        contents,
        mapping={"code": "code", "name": "name"},
    )

    assert response.status_code == 200
    preview = response.json()
    assert preview["can_commit"] is False
    assert preview["summary"]["failed"] == 2
    assert [error["row_number"] for error in preview["errors"]] == [3, 4]
    assert "Duplicate identifier" in preview["errors"][0]["message"]
    assert "code is required" in preview["errors"][1]["message"]


def test_duplicates_are_skipped_or_updated_only_after_preview(
    faculty_import_client,
    auth_env,
):
    first_content = csv_file(["code", "name"], [["ECE", "Electronics"]])
    mapping = {"code": "code", "name": "name"}
    first = upload_preview(
        faculty_import_client,
        first_content,
        mapping=mapping,
    ).json()
    assert commit_preview(faculty_import_client, first).status_code == 200

    changed_content = csv_file(["code", "name"], [["ECE", "Electronics & Communication"]])
    skipped = upload_preview(
        faculty_import_client,
        changed_content,
        mapping=mapping,
        duplicate_policy="skip",
    ).json()
    assert skipped["summary"]["skipped"] == 1
    assert commit_preview(faculty_import_client, skipped).json()["summary"]["skipped"] == 1
    with auth_env["session_factory"]() as db:
        assert db.scalar(select(Department).where(Department.code == "ECE")).name == "Electronics"

    update = upload_preview(
        faculty_import_client,
        changed_content,
        mapping=mapping,
        duplicate_policy="update",
    ).json()
    assert update["summary"]["updated"] == 1
    result = commit_preview(faculty_import_client, update)
    assert result.status_code == 200
    assert result.json()["summary"]["updated"] == 1
    with auth_env["session_factory"]() as db:
        assert db.scalar(select(Department).where(Department.code == "ECE")).name == "Electronics & Communication"


def test_update_preview_rejects_stale_existing_record(
    faculty_import_client,
    auth_env,
):
    initial = upload_preview(
        faculty_import_client,
        csv_file(["Code", "Name"], [["ARC", "Architecture"]]),
        import_type="departments",
        mapping={"code": "Code", "name": "Name"},
    ).json()
    assert commit_preview(faculty_import_client, initial).status_code == 200

    update = upload_preview(
        faculty_import_client,
        csv_file(["Code", "Name"], [["ARC", "Architecture and Design"]]),
        import_type="departments",
        duplicate_policy="update",
        mapping={"code": "Code", "name": "Name"},
    ).json()
    assert update["records"][0]["before"]["name"] == "Architecture"

    with auth_env["session_factory"]() as db:
        department = db.scalar(select(Department).where(Department.code == "ARC"))
        department.name = "Architecture, edited after preview"
        db.commit()

    response = commit_preview(faculty_import_client, update)

    assert response.status_code == 409
    assert "changed after preview" in response.json()["detail"]
    with auth_env["session_factory"]() as db:
        assert db.scalar(select(Department).where(Department.code == "ARC")).name == (
            "Architecture, edited after preview"
        )


def test_structure_imports_resolve_faculty_owned_relationships(faculty_import_client, auth_env):
    year_file = csv_file(
        ["Academic Year", "Start", "End"],
        [["2028-29", "2028-07-01", "2029-06-30"]],
    )
    year_preview = upload_preview(
        faculty_import_client,
        year_file,
        import_type="academic_years",
        mapping={"name": "Academic Year", "start_date": "Start", "end_date": "End"},
    ).json()
    assert commit_preview(faculty_import_client, year_preview).status_code == 200

    department_file = csv_file(["Code", "Name"], [["ENG", "Engineering"]])
    department_preview = upload_preview(
        faculty_import_client,
        department_file,
        import_type="departments",
        mapping={"code": "Code", "name": "Name"},
    ).json()
    assert commit_preview(faculty_import_client, department_preview).status_code == 200

    branch_file = csv_file(
        ["Department", "Branch Code", "Branch Name"],
        [["ENG", "ME", "Mechanical"]],
    )
    branch_preview = upload_preview(
        faculty_import_client,
        branch_file,
        import_type="branches",
        mapping={
            "department_code": "Department",
            "code": "Branch Code",
            "name": "Branch Name",
        },
    ).json()
    assert branch_preview["summary"]["failed"] == 0
    assert commit_preview(faculty_import_client, branch_preview).status_code == 200

    semester_file = csv_file(
        ["Year", "Number", "Term"],
        [["2028-29", "1", "First Semester"]],
    )
    semester_preview = upload_preview(
        faculty_import_client,
        semester_file,
        import_type="semesters",
        mapping={"academic_year": "Year", "number": "Number", "name": "Term"},
    ).json()
    assert commit_preview(faculty_import_client, semester_preview).status_code == 200

    section_file = csv_file(
        ["Branch", "Year", "Semester", "Section"],
        [["ME", "2028-29", "1", "B"]],
    )
    section_preview = upload_preview(
        faculty_import_client,
        section_file,
        import_type="class_sections",
        mapping={
            "branch_code": "Branch",
            "academic_year": "Year",
            "semester_number": "Semester",
            "name": "Section",
        },
    ).json()
    assert commit_preview(faculty_import_client, section_preview).status_code == 200

    subject_file = csv_file(
        ["Branch", "Year", "Semester", "Code", "Name", "Credits"],
        [["ME", "2028-29", "1", "ME101", "Engineering Mechanics", "3.5"]],
    )
    subject_preview = upload_preview(
        faculty_import_client,
        subject_file,
        import_type="subjects",
        mapping={
            "branch_code": "Branch",
            "academic_year": "Year",
            "semester_number": "Semester",
            "code": "Code",
            "name": "Name",
            "credits": "Credits",
        },
    ).json()
    assert subject_preview["summary"]["failed"] == 0
    assert commit_preview(faculty_import_client, subject_preview).status_code == 200

    with auth_env["session_factory"]() as db:
        assert db.scalar(select(AcademicYear).where(AcademicYear.name == "2028-29"))
        assert db.scalar(select(Branch).where(Branch.code == "ME"))
        assert db.scalar(select(Semester).where(Semester.name == "First Semester"))
        assert db.scalar(select(ClassSection).where(ClassSection.name == "B"))
        subject = db.scalar(select(Subject).where(Subject.code == "ME101"))
        assert subject.credits == Decimal("3.5")


def test_enrollment_import_uses_existing_student_and_assigned_section(
    faculty_import_client,
    auth_env,
):
    _, _, branch, _, _ = create_structure(faculty_import_client)
    student_created = faculty_import_client.post(
        "/api/faculty/students",
        json={
            "student_id": "STU-ENROLL-2",
            "full_name": "Enrollment Learner",
            "email": "enroll@example.edu",
            "section_id": faculty_import_client.get("/api/faculty/sections").json()[0]["id"],
        },
    )
    assert student_created.status_code == 201
    content = csv_file(
        ["Student", "Branch", "Year", "Semester", "Section", "Status"],
        [["STU-ENROLL-2", branch["code"], "2026-27", 1, "A", "completed"]],
    )
    response = upload_preview(
        faculty_import_client,
        content,
        import_type="enrollments",
        duplicate_policy="update",
        mapping={
            "student_id": "Student",
            "branch_code": "Branch",
            "academic_year": "Year",
            "semester_number": "Semester",
            "section_name": "Section",
            "status": "Status",
        },
    )
    assert response.status_code == 200
    assert response.json()["summary"]["updated"] == 1, (
        response.json()["summary"],
        response.json()["errors"],
        response.json()["records"],
    )
    result = commit_preview(faculty_import_client, response.json())
    assert result.status_code == 200
    with auth_env["session_factory"]() as db:
        enrollment = db.scalar(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id == "STU-ENROLL-2"
            )
        )
        assert enrollment.status == "completed"


def test_commit_requires_explicit_confirmation_and_is_single_use(faculty_import_client):
    content = csv_file(["Code", "Name"], [["IT", "Information Technology"]])
    preview = upload_preview(
        faculty_import_client,
        content,
        import_type="departments",
        mapping={"code": "Code", "name": "Name"},
    ).json()
    missing_confirmation = faculty_import_client.post(
        "/api/faculty/imports/commit",
        json={"preview_id": preview["preview_id"], "confirm": False},
    )
    assert missing_confirmation.status_code == 422
    assert commit_preview(faculty_import_client, preview).status_code == 200
    assert commit_preview(faculty_import_client, preview).status_code == 404


def test_transaction_rolls_back_every_row_on_commit_failure(
    faculty_import_client,
    auth_env,
    monkeypatch,
):
    content = csv_file(
        ["Code", "Name"],
        [["LAW", "Law"], ["PHL", "Philosophy"]],
    )
    preview = upload_preview(
        faculty_import_client,
        content,
        import_type="departments",
        mapping={"code": "Code", "name": "Name"},
    ).json()
    original_new_record = faculty_import_service._new_record
    calls = 0

    def fail_after_first_row(db, import_type, values, user_id):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SQLAlchemyError("simulated database failure")
        return original_new_record(db, import_type, values, user_id)

    monkeypatch.setattr(faculty_import_service, "_new_record", fail_after_first_row)
    response = commit_preview(faculty_import_client, preview)

    assert response.status_code == 409
    assert "No rows were committed" in response.json()["detail"]
    with auth_env["session_factory"]() as db:
        imported = db.scalar(
            select(func.count())
            .select_from(Department)
            .where(Department.code.in_(("LAW", "PHL")))
        )
        assert imported == 0


def test_preview_cannot_be_committed_by_a_different_faculty_account(
    faculty_import_client,
    auth_env,
):
    content = csv_file(["Code", "Name"], [["MAT", "Mathematics"]])
    preview = upload_preview(
        faculty_import_client,
        content,
        import_type="departments",
        mapping={"code": "Code", "name": "Name"},
    ).json()
    token = __import__("app.core.security", fromlist=["create_session_token"]).create_session_token()
    other_id = str(uuid4())
    from app.core.security import hash_password, hash_session_token
    from app.models.auth import AuthSession, FacultyAccount, UserAccount
    from datetime import datetime, timedelta, timezone

    with auth_env["session_factory"]() as db:
        other = UserAccount(
            id=other_id,
            email="import-other-faculty@example.edu",
            password_hash=hash_password("Other-Import-Password-12"),
            role="faculty",
        )
        other.faculty_account = FacultyAccount(
            faculty_code="FAC-IMPORT-OTHER",
            full_name="Other Import Faculty",
        )
        other.sessions.append(
            AuthSession(
                id=str(uuid4()),
                token_hash=hash_session_token(token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.add(other)
        db.commit()

    faculty_import_client.cookies.set(AUTH_COOKIE_NAME, token, path="/api")
    response = commit_preview(faculty_import_client, preview)
    assert response.status_code == 404


def test_xlsx_formula_cells_are_rejected(faculty_import_client):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Code", "Name"])
    worksheet.append(["=1+2", "Calculated"])
    content = io.BytesIO()
    workbook.save(content)

    response = upload_preview(
        faculty_import_client,
        content.getvalue(),
        filename="formula.xlsx",
    )

    assert response.status_code == 422
    assert "Formula cells are not allowed" in response.json()["detail"]
