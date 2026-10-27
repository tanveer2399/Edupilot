from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_faculty_record, get_student_record, require_faculty, require_student
from app.database import get_db
from app.models.auth import UserAccount
from app.schemas.academic import MarkCreate, MarkResponse
from app.services.academic_service import (
    list_marks,
)

router = APIRouter(prefix="/marks", tags=["marks"])


@router.get("", response_model=list[MarkResponse])
def read_marks(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_student),
):
    student = get_student_record(user, db)
    return list_marks(db, student.student_id)

@router.post("", response_model=MarkResponse, status_code=status.HTTP_201_CREATED)
def add_mark(
    values: MarkCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    get_faculty_record(user, db)
    raise HTTPException(status_code=403, detail="Use class-scoped faculty marks entry.")
