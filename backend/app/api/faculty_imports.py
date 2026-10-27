import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.auth import get_faculty_record, require_faculty
from app.database import get_db
from app.models.auth import UserAccount
from app.services.faculty_import_service import (
    MAX_IMPORT_BYTES,
    ImportCommitError,
    ImportFileError,
    commit_import,
    import_fields,
    prepare_import_preview,
)

router = APIRouter(prefix="/faculty/imports", tags=["faculty data import"])


class ImportCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: UUID
    confirm: Literal[True]


@router.get("/types")
def list_import_types(
    user: UserAccount = Depends(require_faculty),
    db: Session = Depends(get_db),
):
    get_faculty_record(user, db)
    return {
        import_type: import_fields(import_type)
        for import_type in (
            "students",
            "academic_years",
            "departments",
            "branches",
            "semesters",
            "class_sections",
            "subjects",
            "enrollments",
        )
    }


@router.post("/preview")
async def create_import_preview(
    file: UploadFile = File(...),
    import_type: str = Form(...),
    duplicate_policy: Literal["skip", "update"] = Form("skip"),
    mapping: str = Form(""),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    get_faculty_record(user, db)
    content = await file.read(MAX_IMPORT_BYTES + 1)
    await file.close()
    try:
        parsed_mapping = None
        if mapping.strip():
            try:
                parsed_mapping = json.loads(mapping)
            except json.JSONDecodeError as error:
                raise ImportFileError("Column mapping must be valid JSON.") from error
            if (
                not isinstance(parsed_mapping, dict)
                or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in parsed_mapping.items()
                )
            ):
                raise ImportFileError(
                    "Column mapping must map import field names to column headers."
                )
        return prepare_import_preview(
            db,
            filename=file.filename,
            content=content,
            import_type=import_type,
            mapping=parsed_mapping,
            duplicate_policy=duplicate_policy,
            user_id=user.id,
        )
    except ImportFileError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/commit")
def confirm_import(
    values: ImportCommitRequest,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(require_faculty),
):
    get_faculty_record(user, db)
    try:
        summary = commit_import(
            db,
            preview_id=values.preview_id,
            user_id=user.id,
        )
    except ImportFileError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ImportCommitError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return {
        "status": "completed",
        "summary": summary,
    }
