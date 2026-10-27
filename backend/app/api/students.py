from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, get_student_record, require_student
from app.database import get_db
from app.schemas.student import StudentResponse
from app.models.auth import UserAccount

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me", response_model=StudentResponse)
def read_current_student(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_student),
):
    return get_student_record(user, db)
