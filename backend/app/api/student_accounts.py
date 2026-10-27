from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.auth import get_faculty_record, require_faculty
from app.database import get_db
from app.models.auth import UserAccount
from app.services.student_account_service import (
    StudentAccountProvisioningError,
    provision_section_student_accounts,
)

router = APIRouter(prefix="/faculty/student-accounts", tags=["faculty student accounts"])


class StudentAccountProvisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: int = Field(gt=0)


@router.post("/provision")
def provision_student_accounts(
    values: StudentAccountProvisionRequest,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    get_faculty_record(user, db)
    try:
        return provision_section_student_accounts(
            db,
            section_id=values.section_id,
            faculty_user_id=user.id,
        )
    except StudentAccountProvisioningError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
