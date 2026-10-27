from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_faculty_record, get_student_record, require_faculty, require_student
from app.database import get_db
from app.models.auth import UserAccount
from app.schemas.academic import AssignmentCreate, AssignmentResponse
from app.services.academic_service import (
    assignment_response,
    get_assignment,
    list_assignments,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("", response_model=list[AssignmentResponse])
def read_assignments(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_student),
):
    student = get_student_record(user, db)
    return [
        assignment_response(record)
        for record in list_assignments(db, student.student_id)
    ]


@router.get("/{assignment_id}", response_model=AssignmentResponse)
def read_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_student),
):
    student = get_student_record(user, db)
    record = get_assignment(db, student.student_id, assignment_id)
    return assignment_response(record)


@router.post(
    "",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_assignment(
    values: AssignmentCreate,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    get_faculty_record(user, db)
    raise HTTPException(
        status_code=403,
        detail="Use class-scoped faculty assignment management.",
    )
