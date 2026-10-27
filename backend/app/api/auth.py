from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import AUTH_COOKIE_NAME, AUTH_COOKIE_SECURE, AUTH_SESSION_TTL_HOURS
from app.core.security import create_session_token, hash_session_token, verify_password
from app.database import get_db
from app.models.auth import AuthSession, FacultyAccount, StudentAccount, UserAccount
from app.models.student import Student
from app.schemas.auth import (
    LoginRequest,
    StudentPasswordSetupRequest,
    UserResponse,
)
from app.services.student_account_service import (
    StudentAccountProvisioningError,
    set_student_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> UserAccount:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in to continue.",
            headers={"WWW-Authenticate": "Cookie"},
        )

    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_session_token(token),
            AuthSession.revoked_at.is_(None),
        )
    )
    now = datetime.now(timezone.utc)
    if auth_session is None or _as_utc(auth_session.expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        )
    if not auth_session.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is disabled.",
        )
    return auth_session.user


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def require_student(user: UserAccount = Depends(get_current_user)) -> UserAccount:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="A student account is required.")
    return user


def require_faculty(user: UserAccount = Depends(get_current_user)) -> UserAccount:
    if user.role != "faculty":
        raise HTTPException(status_code=403, detail="A faculty account is required.")
    return user


def get_student_record(user: UserAccount, db: Session) -> Student:
    account = db.get(StudentAccount, user.id)
    if account is None or account.student.is_demo:
        raise HTTPException(
            status_code=403,
            detail="This account is not linked to an active student profile.",
        )
    return account.student


def get_faculty_record(user: UserAccount, db: Session) -> FacultyAccount:
    account = db.get(FacultyAccount, user.id)
    if account is None:
        raise HTTPException(
            status_code=403,
            detail="This account is not linked to a faculty profile.",
        )
    return account


def reject_unscoped_faculty_write(
    user: UserAccount = Depends(require_faculty),
) -> None:
    raise HTTPException(
        status_code=403,
        detail=(
            "Faculty data entry is unavailable until this account is assigned "
            "to the class or subject."
        ),
    )


@router.post("/login", response_model=UserResponse)
def login(values: LoginRequest, response: Response, db: Session = Depends(get_db)):
    identifier = values.email.strip()
    user = db.scalar(
        select(UserAccount).where(UserAccount.email == identifier.casefold())
    )
    if user is None and "@" not in identifier:
        user = db.scalar(
            select(UserAccount)
            .join(StudentAccount, StudentAccount.user_id == UserAccount.id)
            .join(Student, Student.student_id == StudentAccount.student_id)
            .where(Student.student_id == identifier)
        )
    if (
        user is None
        or not user.is_active
        or user.password_setup_required
        or not verify_password(values.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
        )

    token = create_session_token()
    now = datetime.now(timezone.utc)
    auth_session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=now + timedelta(hours=AUTH_SESSION_TTL_HOURS),
    )
    db.add(auth_session)
    db.commit()
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_SESSION_TTL_HOURS * 60 * 60,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/api",
    )
    return _user_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        auth_session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == hash_session_token(token),
                AuthSession.revoked_at.is_(None),
            )
        )
        if auth_session is not None:
            auth_session.revoked_at = datetime.now(timezone.utc)
            db.commit()
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/api",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/student/setup", status_code=status.HTTP_204_NO_CONTENT)
def complete_student_password_setup(
    values: StudentPasswordSetupRequest,
    db: Session = Depends(get_db),
):
    try:
        set_student_password(db, token=values.token, password=values.password)
    except StudentAccountProvisioningError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def read_current_user(user: UserAccount = Depends(get_current_user)):
    return _user_response(user)


def _user_response(user: UserAccount) -> UserResponse:
    if user.role == "student":
        display_name = user.student_account.student.full_name if user.student_account else ""
    else:
        display_name = user.faculty_account.full_name if user.faculty_account else ""
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=display_name,
    )
