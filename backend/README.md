# EduPilot backend

FastAPI API with SQLAlchemy and a local SQLite database.

## PowerShell setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`; Swagger UI is at
`http://127.0.0.1:8000/docs`. The database, sample student, and academic
development records are initialized automatically on startup.

## Seed test-student academic records (development only)

The student dashboard and Study Assistant read records by the student's exact
`student_id`; enrollment alone does not attach academic records. To preview a
small set of attendance, marks, assignments, and timetable entries for one
existing test student, run this command from the `backend` directory:

```powershell
python -m app.cli seed-test-academics --student-id "YOUR-EXACT-STUDENT-ID"
```

This command is a dry run by default and does not write records. It refuses to
run unless `APP_ENV` is `development`, the configured and connected database
are the backend's local `edupilot.db` SQLite file, and the exact student has a
non-demo profile, active student login link, and active enrollment. It neither
creates accounts nor sends email.

Review the dry-run counts first. Only after explicitly approving the inserts,
add `--apply`:

```powershell
python -m app.cli seed-test-academics --student-id "YOUR-EXACT-STUDENT-ID" --apply
```

The command inserts records only for that exact student ID. It never updates or
deletes existing data; existing natural keys are skipped on each run. The
sample attendance dates and assessment names are stable, while assignment due
dates are relative to the first successful run and remain unchanged on reruns.
Automated seed tests use isolated temporary SQLite databases.

## Study Assistant (local Ollama)

Install Ollama, start its local service, and download the default lightweight
model:

```powershell
ollama pull qwen2.5:1.5b
```

The backend uses `http://127.0.0.1:11434` and `qwen2.5:1.5b` by default. To
change these settings, edit `OLLAMA_BASE_URL` or `OLLAMA_MODEL` in `backend/.env`.
No cloud API key is needed. The Study Assistant is available at
`POST /api/study-assistant/chat`; recent conversation context is kept in backend
memory and is cleared when the backend restarts.

## AI Quiz Generator

The Study Planner page uses the local Ollama model to generate practice
questions. Generate a quiz with `POST /api/quiz/generate`, providing a topic or
study notes, an optional question count (5, 10, or 15), and a difficulty
(`easy`, `medium`, or `hard`). Submit answers to
`POST /api/quiz/{quiz_id}/submit`. Correct answers and explanations are kept
server-side until submission.

After submission, students can request a focused review plan based on missed
answers. Plans are validated and generated with the same local Ollama model;
they are not saved and are available only with the active in-memory quiz
session. This user-triggered, bounded workflow is agent-like, not an
autonomous agent.

Quiz sessions are held in backend memory for up to one hour (with a maximum
of 100 active quizzes). They are cleared when the backend restarts and are not
shared between multiple backend workers. If Ollama returns invalid quiz data
twice, the API reports an error rather than displaying or scoring invalid
questions.

Run tests with `python -m pytest`.
