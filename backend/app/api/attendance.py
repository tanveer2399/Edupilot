from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import (
    get_faculty_record,
    get_student_record,
    require_faculty,
    require_student,
)
from app.database import get_db
from app.models.auth import UserAccount
from app.schemas.academic import (
    AttendanceCreate,
    AttendanceResponse,
    AttendanceSummaryResponse,
)
from app.services.academic_service import (
    list_attendance,
    summarize_attendance,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("", response_model=list[AttendanceResponse])
def read_attendance(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_student),
):
    student = get_student_record(user, db)
    return list_attendance(db, student.student_id)


@router.get("/summary", response_model=AttendanceSummaryResponse)
def read_attendance_summary(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_student),
):
    student = get_student_record(user, db)
    records = list_attendance(db, student.student_id)
    return summarize_attendance(records)


@router.post(
    "",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_attendance(
    values: AttendanceCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    get_faculty_record(user, db)
    raise HTTPException(
        status_code=403,
        detail="Use class-scoped faculty attendance entry.",
    )
