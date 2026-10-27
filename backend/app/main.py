from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from alembic import command
from alembic.config import Config

import app.models
from app.api import (
    assignments,
    auth,
    attendance,
    dashboard,
    faculty,
    faculty_imports,
    health,
    marks,
    quiz,
    student_accounts,
    students,
    study_assistant,
    timetable,
)
from app.core.config import BACKEND_DIR, CORS_ORIGINS, SEED_DEMO_DATA
from app.database import SessionLocal, engine
from app.services.academic_seed_service import ensure_sample_academic_data
from app.services.student_service import ensure_sample_student


@asynccontextmanager
async def lifespan(_: FastAPI):
    migration_config = Config(str(BACKEND_DIR / "alembic.ini"))
    migration_config.attributes["configure_logger"] = False
    command.upgrade(migration_config, "head")
    if SEED_DEMO_DATA:
        with SessionLocal() as db:
            ensure_sample_student(db)
            ensure_sample_academic_data(db)
    yield


app = FastAPI(
    title="EduPilot API",
    description="College academic management and student portal API.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def validate_request_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and origin is not None
        and origin not in CORS_ORIGINS
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": "Requests from this origin are not allowed."},
        )
    return await call_next(request)


app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(faculty.router, prefix="/api")
app.include_router(faculty_imports.router, prefix="/api")
app.include_router(student_accounts.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(marks.router, prefix="/api")
app.include_router(assignments.router, prefix="/api")
app.include_router(timetable.router, prefix="/api")
app.include_router(study_assistant.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")
