from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_student
from app.models.auth import UserAccount

from app.schemas.quiz import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    StudyPlanResponse,
)
from app.services.quiz_service import (
    QuizError,
    generate_quiz,
    generate_study_plan,
    submit_quiz,
)

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.post("/generate", response_model=QuizGenerateResponse)
async def create_quiz(
    values: QuizGenerateRequest,
    user: UserAccount = Depends(require_student),
):
    try:
        return await generate_quiz(values, user.id)
    except QuizError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error


@router.post("/{quiz_id}/submit", response_model=QuizSubmitResponse)
def submit_quiz_answers(
    quiz_id: UUID,
    values: QuizSubmitRequest,
    user: UserAccount = Depends(require_student),
):
    try:
        return submit_quiz(quiz_id, values.answers, user.id)
    except QuizError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error


@router.post("/{quiz_id}/study-plan", response_model=StudyPlanResponse)
async def create_study_plan(
    quiz_id: UUID,
    user: UserAccount = Depends(require_student),
):
    try:
        return await generate_study_plan(quiz_id, user.id)
    except QuizError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error
