from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_student_record, require_student
from app.database import get_db
from app.models.auth import UserAccount
from app.schemas.study_assistant import ChatRequest, ChatResponse
from app.services.student_academic_context_service import (
    academic_context_categories,
    build_student_academic_context,
)
from app.services.study_assistant_service import (
    StudyAssistantError,
    chat_with_tutor,
    get_conversation_history,
)

router = APIRouter(prefix="/study-assistant", tags=["study assistant"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    values: ChatRequest,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_student),
):
    try:
        history = get_conversation_history(values.conversation_id, user.id)
        categories = academic_context_categories(values.message, history)
        academic_context = None
        if categories:
            student = get_student_record(user, db)
            academic_context = build_student_academic_context(
                db,
                student,
                categories,
            )
        answer, conversation_id = await chat_with_tutor(
            values.message,
            values.conversation_id,
            user.id,
            academic_context,
        )
    except StudyAssistantError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error

    return ChatResponse(answer=answer, conversation_id=conversation_id)
