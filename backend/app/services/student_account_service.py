import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core import config
from app.core.security import create_session_token, hash_password, hash_session_token
from app.models.academic_structure import (
    ClassSection,
    FacultySectionAssignment,
    StudentEnrollment,
)
from app.models.auth import (
    AuthSession,
    StudentAccount,
    StudentPasswordSetupToken,
    UserAccount,
)
from app.models.student import Student

logger = logging.getLogger(__name__)
email_adapter = TypeAdapter(EmailStr)


class StudentAccountProvisioningError(RuntimeError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def _setup_delivery_mode() -> str:
    smtp_core_configured = bool(config.SMTP_HOST and config.SMTP_FROM_EMAIL)
    smtp_partial = bool(config.SMTP_HOST) != bool(config.SMTP_FROM_EMAIL)
    smtp_auth_partial = bool(config.SMTP_USERNAME) != bool(config.SMTP_PASSWORD)
    if smtp_partial or smtp_auth_partial:
        raise StudentAccountProvisioningError(
            "Email delivery configuration is incomplete.", 503
        )
    if smtp_core_configured:
        return "email"
    if config.APP_ENV == "development" and config.ALLOW_LOCAL_STUDENT_SETUP_LINKS:
        return "local"
    raise StudentAccountProvisioningError(
        "Configure SMTP delivery or explicitly enable local development setup links.",
        503,
    )


def _setup_url(token: str) -> str:
    return (
        f"{config.FRONTEND_BASE_URL}/student-setup"
        f"?token={quote(token, safe='')}"
    )


def _send_setup_email(email: str, student_name: str, setup_url: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Set up your EduPilot student account"
    message["From"] = config.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        f"Hello {student_name},\n\n"
        "A student login has been created for you. Set your password using "
        f"this one-time link:\n{setup_url}\n\n"
        f"This link expires in {config.STUDENT_SETUP_TOKEN_TTL_HOURS} hours "
        "and can only be used once.\n"
    )
    if config.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
            if config.SMTP_USERNAME:
                smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            smtp.send_message(message)
        return
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
        if config.SMTP_USE_STARTTLS:
            smtp.starttls()
        if config.SMTP_USERNAME:
            smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        smtp.send_message(message)


def _issue_setup_token(
    db: Session,
    user: UserAccount,
) -> tuple[StudentPasswordSetupToken, str]:
    token = create_session_token()
    record = db.scalar(
        select(StudentPasswordSetupToken).where(
            StudentPasswordSetupToken.user_id == user.id
        )
    )
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=config.STUDENT_SETUP_TOKEN_TTL_HOURS
    )
    if record is None:
        record = StudentPasswordSetupToken(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
        )
        db.add(record)
    else:
        record.token_hash = hash_session_token(token)
        record.expires_at = expires_at
        record.used_at = None
        record.created_at = datetime.now(timezone.utc)
    return record, token


def provision_section_student_accounts(
    db: Session,
    *,
    section_id: int,
    faculty_user_id: str,
) -> dict[str, Any]:
    assignment = db.scalar(
        select(FacultySectionAssignment.section_id).where(
            FacultySectionAssignment.section_id == section_id,
            FacultySectionAssignment.faculty_user_id == faculty_user_id,
        )
    )
    if assignment is None:
        raise StudentAccountProvisioningError(
            "Class section not found in your faculty scope.", 404
        )
    section = db.get(ClassSection, section_id)
    if section is None:
        raise StudentAccountProvisioningError(
            "Class section not found in your faculty scope.", 404
        )
    delivery_mode = _setup_delivery_mode()

    students = list(
        db.execute(
            select(Student, StudentEnrollment.status)
            .join(
                StudentEnrollment,
                StudentEnrollment.student_id == Student.student_id,
            )
            .where(StudentEnrollment.section_id == section_id)
            .order_by(Student.student_id)
        )
    )
    summary = {
        "created": 0,
        "already_linked": 0,
        "skipped": 0,
        "failed": 0,
        "delivery_failed": 0,
    }
    results = []
    local_setup_links = []

    for student, enrollment_status in students:
        if enrollment_status != "active" or student.is_demo:
            summary["skipped"] += 1
            results.append(
                {"student_id": student.student_id, "status": "skipped"}
            )
            continue
        try:
            email = str(email_adapter.validate_python(student.email)).casefold()
        except ValidationError:
            summary["skipped"] += 1
            results.append(
                {
                    "student_id": student.student_id,
                    "status": "skipped",
                    "reason": "Student record has no valid email address.",
                }
            )
            continue

        link = db.scalar(
            select(StudentAccount).where(
                StudentAccount.student_id == student.student_id
            )
        )
        token: str | None = None
        if link is not None:
            user = db.get(UserAccount, link.user_id)
            if user is None or user.role != "student" or not user.is_active:
                summary["failed"] += 1
                results.append(
                    {
                        "student_id": student.student_id,
                        "status": "failed",
                        "reason": "Existing student account link is inconsistent.",
                    }
                )
                continue
            summary["already_linked"] += 1
            if user.password_setup_required:
                try:
                    _, token = _issue_setup_token(db, user)
                    db.commit()
                except SQLAlchemyError as error:
                    db.rollback()
                    summary["failed"] += 1
                    summary["already_linked"] -= 1
                    results.append(
                        {
                            "student_id": student.student_id,
                            "status": "failed",
                            "reason": "Could not refresh the password setup link.",
                        }
                    )
                    logger.warning(
                        "Student setup token refresh failed: %s", type(error).__name__
                    )
                    continue
            else:
                results.append(
                    {"student_id": student.student_id, "status": "already_linked"}
                )
                continue
            result_status = "already_linked"
        else:
            existing_email_user = db.scalar(
                select(UserAccount).where(
                    func.lower(UserAccount.email) == email
                )
            )
            if existing_email_user is not None:
                summary["failed"] += 1
                results.append(
                    {
                        "student_id": student.student_id,
                        "status": "failed",
                        "reason": "Email address is already registered to another account.",
                    }
                )
                continue
            try:
                user = UserAccount(
                    id=str(uuid4()),
                    email=email,
                    password_hash=hash_password(create_session_token()),
                    role="student",
                    password_setup_required=True,
                )
                db.add(user)
                db.flush()
                db.add(StudentAccount(user_id=user.id, student_id=student.student_id))
                _, token = _issue_setup_token(db, user)
                db.commit()
            except (IntegrityError, SQLAlchemyError) as error:
                db.rollback()
                summary["failed"] += 1
                results.append(
                    {
                        "student_id": student.student_id,
                        "status": "failed",
                        "reason": "Account creation conflicted with an existing record.",
                    }
                )
                logger.warning(
                    "Student account provisioning failed: %s", type(error).__name__
                )
                continue
            summary["created"] += 1
            result_status = "created"

        if token is None:
            summary["failed"] += 1
            results.append(
                {
                    "student_id": student.student_id,
                    "status": "failed",
                    "reason": "Could not create a password setup link.",
                }
            )
            continue
        setup_url = _setup_url(token)
        if delivery_mode == "email":
            try:
                _send_setup_email(email, student.full_name, setup_url)
            except (OSError, smtplib.SMTPException) as error:
                summary["delivery_failed"] += 1
                results.append(
                    {
                        "student_id": student.student_id,
                        "status": "delivery_failed",
                        "reason": "Account is ready, but setup email could not be sent. Retry provisioning to send a fresh link.",
                    }
                )
                logger.warning(
                    "Student setup email delivery failed: %s", type(error).__name__
                )
            else:
                results.append(
                    {
                        "student_id": student.student_id,
                        "status": result_status,
                        "setup_email_sent": True,
                    }
                )
        else:
            local_setup_links.append(
                {
                    "student_id": student.student_id,
                    "url": setup_url,
                }
            )
            results.append(
                {
                    "student_id": student.student_id,
                    "status": result_status,
                    "setup_link_available": True,
                }
            )

    response = {
        "section_id": section_id,
        "summary": summary,
        "results": results,
        "delivery_mode": delivery_mode,
    }
    if delivery_mode == "local":
        response["local_development_only"] = True
        response["local_setup_links"] = local_setup_links
    return response


def set_student_password(db: Session, *, token: str, password: str) -> None:
    now = datetime.now(timezone.utc)
    record = db.scalar(
        select(StudentPasswordSetupToken).where(
            StudentPasswordSetupToken.token_hash == hash_session_token(token)
        )
    )
    if record is None or record.used_at is not None:
        raise StudentAccountProvisioningError(
            "This password setup link is invalid or has already been used.", 400
        )
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise StudentAccountProvisioningError(
            "This password setup link has expired. Ask faculty to send a new one.",
            400,
        )
    user = db.get(UserAccount, record.user_id)
    if (
        user is None
        or user.role != "student"
        or not user.is_active
        or not user.password_setup_required
    ):
        raise StudentAccountProvisioningError(
            "This password setup link is invalid or has already been used.", 400
        )
    consumed = db.execute(
        update(StudentPasswordSetupToken)
        .where(
            StudentPasswordSetupToken.id == record.id,
            StudentPasswordSetupToken.used_at.is_(None),
            StudentPasswordSetupToken.expires_at > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if consumed.rowcount != 1:
        db.rollback()
        raise StudentAccountProvisioningError(
            "This password setup link is invalid or has already been used.", 400
        )
    user.password_hash = hash_password(password)
    user.password_setup_required = False
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    db.commit()
