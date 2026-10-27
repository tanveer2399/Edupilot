from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_student_record, require_student
from app.database import get_db
from app.models.auth import UserAccount
from app.schemas.dashboard import DashboardResponse
from app.services.academic_service import get_sample_student
from app.services.dashboard_service import get_dashboard_data

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def read_dashboard(
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_student),
):
    student = get_student_record(user, db)
    return get_dashboard_data(db, student.student_id)
