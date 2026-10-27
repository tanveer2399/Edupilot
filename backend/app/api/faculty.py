from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import get_faculty_record, require_faculty
from app.database import get_db
from app.models.academic_structure import (
    AcademicYear,
    Branch,
    ClassSection,
    Department,
    FacultySectionAssignment,
    Semester,
    StudentEnrollment,
    Subject,
)
from app.models.auth import UserAccount
from app.models.student import Student
from app.schemas.faculty import (
    AcademicYearCreate,
    AcademicYearResponse,
    BranchCreate,
    BranchResponse,
    ClassSectionCreate,
    ClassSectionResponse,
    DepartmentCreate,
    DepartmentResponse,
    FacultyStudentResponse,
    SemesterCreate,
    SemesterResponse,
    StudentCreate,
    StudentUpdate,
    SubjectCreate,
    SubjectResponse,
)

router = APIRouter(prefix="/faculty", tags=["faculty management"])


def _commit_or_conflict(db: Session, description: str) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{description} conflicts with an existing academic record.",
        ) from error


def _owned_record(
    db: Session,
    model: type,
    record_id: int,
    user_id: str,
):
    record = db.scalar(
        select(model).where(
            model.id == record_id,
            model.created_by_user_id == user_id,
        )
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic record not found.",
        )
    return record


def _require_faculty_profile(user: UserAccount, db: Session) -> None:
    get_faculty_record(user, db)


def _save_update(
    db: Session,
    record: object,
    values: dict[str, object],
    description: str,
) -> object:
    for field, value in values.items():
        setattr(record, field, value)
    _commit_or_conflict(db, description)
    db.refresh(record)
    return record


def _section_for_faculty(
    db: Session,
    section_id: int,
    faculty_user_id: str,
) -> tuple[ClassSection, Branch, Semester, AcademicYear]:
    row = db.execute(
        select(ClassSection, Branch, Semester, AcademicYear)
        .join(
            FacultySectionAssignment,
            FacultySectionAssignment.section_id == ClassSection.id,
        )
        .join(Branch, Branch.id == ClassSection.branch_id)
        .join(Semester, Semester.id == ClassSection.semester_id)
        .join(AcademicYear, AcademicYear.id == ClassSection.academic_year_id)
        .where(
            ClassSection.id == section_id,
            FacultySectionAssignment.faculty_user_id == faculty_user_id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Assigned class section not found.")
    return row


def _student_response(
    student: Student,
    enrollment: StudentEnrollment,
    section: ClassSection,
    branch: Branch,
    year: AcademicYear,
    semester: Semester,
) -> FacultyStudentResponse:
    return FacultyStudentResponse(
        student_id=student.student_id,
        full_name=student.full_name,
        email=student.email,
        department=student.department,
        semester=student.semester,
        section_id=section.id,
        section_name=section.name,
        branch_name=branch.name,
        academic_year=year.name,
        semester_name=semester.name,
        enrollment_status=enrollment.status,
        enrolled_at=enrollment.enrolled_at,
    )


@router.get("/academic-years", response_model=list[AcademicYearResponse])
def list_academic_years(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    return list(
        db.scalars(
            select(AcademicYear)
            .where(AcademicYear.created_by_user_id == user.id)
            .order_by(AcademicYear.start_date.desc())
        )
    )


@router.post(
    "/academic-years",
    response_model=AcademicYearResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_academic_year(
    values: AcademicYearCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    record = AcademicYear(**values.model_dump(), created_by_user_id=user.id)
    db.add(record)
    _commit_or_conflict(db, "Academic year")
    db.refresh(record)
    return record


@router.put(
    "/academic-years/{year_id}",
    response_model=AcademicYearResponse,
)
def update_academic_year(
    year_id: int,
    values: AcademicYearCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    record = _owned_record(db, AcademicYear, year_id, user.id)
    return _save_update(db, record, values.model_dump(), "Academic year")


@router.get("/departments", response_model=list[DepartmentResponse])
def list_departments(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    return list(
        db.scalars(
            select(Department)
            .where(Department.created_by_user_id == user.id)
            .order_by(Department.name)
        )
    )


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    values: DepartmentCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    record = Department(
        **values.model_dump(exclude={"code"}),
        code=values.code.upper(),
        created_by_user_id=user.id,
    )
    db.add(record)
    _commit_or_conflict(db, "Department")
    db.refresh(record)
    return record


@router.put(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
)
def update_department(
    department_id: int,
    values: DepartmentCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    record = _owned_record(db, Department, department_id, user.id)
    changes = values.model_dump()
    changes["code"] = values.code.upper()
    return _save_update(db, record, changes, "Department")


@router.get("/branches", response_model=list[BranchResponse])
def list_branches(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    return list(
        db.scalars(
            select(Branch)
            .where(Branch.created_by_user_id == user.id)
            .order_by(Branch.name)
        )
    )


@router.post(
    "/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch(
    values: BranchCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    _owned_record(db, Department, values.department_id, user.id)
    record = Branch(
        **values.model_dump(exclude={"code"}),
        code=values.code.upper(),
        created_by_user_id=user.id,
    )
    db.add(record)
    _commit_or_conflict(db, "Branch")
    db.refresh(record)
    return record


@router.put("/branches/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: int,
    values: BranchCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    record = _owned_record(db, Branch, branch_id, user.id)
    _owned_record(db, Department, values.department_id, user.id)
    changes = values.model_dump()
    changes["code"] = values.code.upper()
    return _save_update(db, record, changes, "Branch")


@router.get("/semesters", response_model=list[SemesterResponse])
def list_semesters(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    return list(
        db.scalars(
            select(Semester)
            .where(Semester.created_by_user_id == user.id)
            .order_by(Semester.academic_year_id, Semester.number)
        )
    )


@router.post(
    "/semesters",
    response_model=SemesterResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_semester(
    values: SemesterCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    _owned_record(db, AcademicYear, values.academic_year_id, user.id)
    record = Semester(**values.model_dump(), created_by_user_id=user.id)
    db.add(record)
    _commit_or_conflict(db, "Semester")
    db.refresh(record)
    return record


@router.put(
    "/semesters/{semester_id}",
    response_model=SemesterResponse,
)
def update_semester(
    semester_id: int,
    values: SemesterCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    record = _owned_record(db, Semester, semester_id, user.id)
    _owned_record(db, AcademicYear, values.academic_year_id, user.id)
    return _save_update(db, record, values.model_dump(), "Semester")


@router.get("/sections", response_model=list[ClassSectionResponse])
def list_sections(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    return list(
        db.scalars(
            select(ClassSection)
            .join(
                FacultySectionAssignment,
                FacultySectionAssignment.section_id == ClassSection.id,
            )
            .where(FacultySectionAssignment.faculty_user_id == user.id)
            .order_by(ClassSection.name)
        )
    )


@router.post(
    "/sections",
    response_model=ClassSectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_section(
    values: ClassSectionCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    branch = _owned_record(db, Branch, values.branch_id, user.id)
    year = _owned_record(db, AcademicYear, values.academic_year_id, user.id)
    semester = _owned_record(db, Semester, values.semester_id, user.id)
    if semester.academic_year_id != year.id:
        raise HTTPException(
            status_code=422,
            detail="The semester must belong to the selected academic year.",
        )
    record = ClassSection(**values.model_dump(), created_by_user_id=user.id)
    db.add(record)
    try:
        db.flush()
        db.add(
            FacultySectionAssignment(
                faculty_user_id=user.id,
                section_id=record.id,
            )
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Class section conflicts with an existing placement.",
        ) from error
    db.refresh(record)
    return record


@router.put("/sections/{section_id}", response_model=ClassSectionResponse)
def update_section(
    section_id: int,
    values: ClassSectionCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    record, _, _, _ = _section_for_faculty(db, section_id, user.id)
    _owned_record(db, Branch, values.branch_id, user.id)
    year = _owned_record(db, AcademicYear, values.academic_year_id, user.id)
    semester = _owned_record(db, Semester, values.semester_id, user.id)
    if semester.academic_year_id != year.id:
        raise HTTPException(
            status_code=422,
            detail="The semester must belong to the selected academic year.",
        )
    return _save_update(db, record, values.model_dump(), "Class section")


@router.get("/subjects", response_model=list[SubjectResponse])
def list_subjects(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    return list(
        db.scalars(
            select(Subject)
            .where(Subject.created_by_user_id == user.id)
            .order_by(Subject.code)
        )
    )


@router.post(
    "/subjects",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_subject(
    values: SubjectCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    _owned_record(db, Branch, values.branch_id, user.id)
    _owned_record(db, Semester, values.semester_id, user.id)
    record = Subject(
        **values.model_dump(exclude={"code"}),
        code=values.code.upper(),
        created_by_user_id=user.id,
    )
    db.add(record)
    _commit_or_conflict(db, "Subject")
    db.refresh(record)
    return record


@router.put("/subjects/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: int,
    values: SubjectCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    record = _owned_record(db, Subject, subject_id, user.id)
    _owned_record(db, Branch, values.branch_id, user.id)
    _owned_record(db, Semester, values.semester_id, user.id)
    changes = values.model_dump()
    changes["code"] = values.code.upper()
    return _save_update(db, record, changes, "Subject")


@router.get("/students", response_model=list[FacultyStudentResponse])
def list_students(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    rows = db.execute(
        select(Student, StudentEnrollment, ClassSection, Branch, AcademicYear, Semester)
        .join(StudentEnrollment, StudentEnrollment.student_id == Student.student_id)
        .join(ClassSection, ClassSection.id == StudentEnrollment.section_id)
        .join(Branch, Branch.id == ClassSection.branch_id)
        .join(AcademicYear, AcademicYear.id == ClassSection.academic_year_id)
        .join(Semester, Semester.id == StudentEnrollment.semester_id)
        .join(
            FacultySectionAssignment,
            FacultySectionAssignment.section_id == ClassSection.id,
        )
        .where(FacultySectionAssignment.faculty_user_id == user.id)
        .order_by(Student.full_name)
    )
    return [
        _student_response(student, enrollment, section, branch, year, semester)
        for student, enrollment, section, branch, year, semester in rows
    ]


@router.post(
    "/students",
    response_model=FacultyStudentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_student(
    values: StudentCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    section, branch, semester, year = _section_for_faculty(
        db,
        values.section_id,
        user.id,
    )
    student = Student(
        student_id=values.student_id,
        full_name=values.full_name,
        email=str(values.email).casefold(),
        department=branch.name,
        semester=semester.number,
        is_demo=False,
    )
    db.add(student)
    try:
        db.flush()
        enrollment = StudentEnrollment(
            student_id=student.student_id,
            section_id=section.id,
            semester_id=semester.id,
        )
        db.add(enrollment)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Student or enrollment conflicts with an existing record.",
        ) from error
    db.refresh(enrollment)
    return _student_response(student, enrollment, section, branch, year, semester)


@router.patch(
    "/students/{student_id}",
    response_model=FacultyStudentResponse,
)
def update_student(
    student_id: str,
    values: StudentUpdate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    _require_faculty_profile(user, db)
    row = db.execute(
        select(Student, StudentEnrollment, ClassSection, Branch, AcademicYear, Semester)
        .join(StudentEnrollment, StudentEnrollment.student_id == Student.student_id)
        .join(ClassSection, ClassSection.id == StudentEnrollment.section_id)
        .join(Branch, Branch.id == ClassSection.branch_id)
        .join(AcademicYear, AcademicYear.id == ClassSection.academic_year_id)
        .join(Semester, Semester.id == StudentEnrollment.semester_id)
        .join(
            FacultySectionAssignment,
            FacultySectionAssignment.section_id == ClassSection.id,
        )
        .where(
            Student.student_id == student_id,
            FacultySectionAssignment.faculty_user_id == user.id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Student record not found.")
    student, enrollment, section, branch, year, semester = row
    student.full_name = values.full_name
    student.email = str(values.email).casefold()
    _commit_or_conflict(db, "Student")
    db.refresh(student)
    return _student_response(student, enrollment, section, branch, year, semester)
