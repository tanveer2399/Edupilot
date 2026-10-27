from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_faculty_record, get_student_record, require_faculty, require_student
from app.database import get_db
from app.models.auth import UserAccount
from app.schemas.academic import TimetableCreate, TimetableResponse
from app.services.academic_service import (
    list_timetable,
)

router = APIRouter(prefix="/timetable", tags=["timetable"])


@router.get("", response_model=list[TimetableResponse])
def read_timetable(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_student),
):
    student = get_student_record(user, db)
    return list_timetable(db, student.student_id)


@router.post(
    "",
    response_model=TimetableResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_timetable_entry(
    values: TimetableCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    get_faculty_record(user, db)
    raise HTTPException(
        status_code=403,
        detail="Use class-scoped faculty timetable management.",
    )
