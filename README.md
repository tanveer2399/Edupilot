# EduPilot

EduPilot is a student portal with a React + Vite frontend, a FastAPI backend,
SQLAlchemy models, and a local SQLite database. It includes a student
dashboard, attendance and marks records, assignments, a timetable, an Ollama
Study Assistant, and an AI quiz generator with answer scoring and review plans.

## Prerequisites

- Python 3.10 or newer
- Node.js 20.19 or newer, or 22.12 or newer
- npm

## Start the backend (PowerShell)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --app-dir .
```

The API is available at `http://127.0.0.1:8000`, with interactive
documentation at `http://127.0.0.1:8000/docs`. The local SQLite database is
created as `backend\edupilot.db` on first startup. Attendance, marks,
assignments, timetable entries, and the sample student profile are stored in
SQLite.

The first faculty account is provisioned locally from the backend directory;
there is no public faculty-registration endpoint:

```powershell
python -m app.cli create-faculty
```

The password is entered through a hidden console prompt and stored as a
password hash. Sign in through the portal using that faculty account.

If PowerShell blocks virtual-environment activation, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal
and activate again.

## Start the frontend (a separate PowerShell terminal)

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend reads its API URL from
`VITE_API_BASE_URL` in `frontend\.env`. Use the sidebar to open attendance,
marks, assignments, timetable, Study Assistant, and Study Planner (the quiz
generator and review planner).

## Faculty Stage 1

The faculty portal currently supports faculty-owned academic years,
departments, branches, semesters, class sections, subjects/credits, and student
enrollment. Faculty API routes are under `/api/faculty`; records are scoped to
their creator, and students are listed or edited only when enrolled in a
section assigned to that faculty account. The schema upgrade is additive and
does not reset existing SQLite records.

The faculty navigation also shows timetable, calendar, attendance, marks, and
assignments as placeholders; their class-management APIs are not yet
implemented. Data Import supports CSV and `.xlsx` uploads for students (with placement),
academic years, departments, branches, semesters, class sections, subjects
and credits, and student enrollments. `POST /api/faculty/imports/preview`
accepts a multipart file, import type, duplicate policy, and optional JSON
column mapping. The first request returns detected headers and sample rows;
the second returns validation errors and a proposed create/update/skip
preview. `POST /api/faculty/imports/commit` requires explicit confirmation and
an unexpired preview ID. The server enforces a 5 MB / 5,000-row limit, validates
relationships in the faculty member's scope, and commits the batch in one
database transaction. Existing records are skipped by default; updates require
choosing the update policy and confirming the displayed current/proposed
values. Previews are kept in process memory for 15 minutes and are invalidated
after use; run a single backend worker or use the same worker for preview and
commit. Student accounts and passwords are never created by import.

Timetable, academic calendar, attendance entry, marks, and assignment
management remain placeholders. Student-account provisioning/linking is a
separate workflow and is not part of file import.

### Student login provisioning

On the faculty **Students** page, choose an assigned class section and select
**Create Student Login Accounts**. The endpoint reuses active enrolled student
records, skips demo profiles or invalid email addresses, and will not link an
email that already belongs to another account. Student accounts and one-time
setup tokens are created atomically per student. Students can sign in with
their exact student ID or registered email after setting a password.
The faculty endpoint is `POST /api/faculty/student-accounts/provision` with
`{ "section_id": <assigned section id> }`; password setup uses
`POST /api/auth/student/setup` with the one-time token and a new password.

Configure SMTP in `backend\.env` (`SMTP_HOST`, `SMTP_FROM_EMAIL`, and optional
`SMTP_USERNAME` / `SMTP_PASSWORD`) to send setup links automatically. SMTP
authentication fields must be supplied together; production SMTP must use TLS.
Setup tokens are valid for 24 hours by default and can only be used once; tune
the lifetime with `STUDENT_SETUP_TOKEN_TTL_HOURS` (1–168).

For local development only, when SMTP is not configured, set
`APP_ENV=development` and `ALLOW_LOCAL_STUDENT_SETUP_LINKS=true`. The faculty
page will then display labelled one-time setup links for manual testing. This
setting is rejected in production and must not be enabled there. Set
`FRONTEND_BASE_URL` to the portal origin when generating links; production
requires an HTTPS URL. If an email delivery attempt fails, the account remains
pending and a later bulk-provisioning attempt rotates the old token and retries
delivery.

The additive migration `0003_student_password_setup` adds the pending-password
flag, setup-token table, and case-insensitive unique email index. Existing
accounts and academic records are preserved. Passwords and setup tokens are
never returned by normal API responses or written to logs.

## AI features and data lifetime

The Study Assistant and quiz generator use the local Ollama service at
`http://127.0.0.1:11434` and default to `qwen2.5:1.5b`. Install Ollama and pull
the model with `ollama pull qwen2.5:1.5b` if needed. Quiz output is parsed and
validated before it is shown; invalid output is retried once and then returned
as an error rather than repaired with invented content.

When a student asks about academic records, `POST /api/study-assistant/chat`
retrieves fresh, authenticated-student-only context for the relevant topic.
Overall performance questions include the profile, attendance, marks,
assignments, and timetable; a general study question does not load those
records. Attendance percentages use recorded sessions only (present and late
count as attended); the database has no scheduled-session ledger to identify
unrecorded classes. Marks averages are weighted by recorded maximum marks.
Official SGPA/CGPA and semester averages are unavailable because marks are not
linked to semesters and no grade-point rules or official results are stored.
Assignment grades/feedback and academic calendar events are not in the current
schema; timetable entries are recurring weekdays and do not include faculty or
dated upcoming sessions. The assistant explains these data gaps instead of
inventing records.

Academic records persist in SQLite across backend restarts. Study Assistant
conversation context and quiz sessions are held in backend memory and are
cleared when it restarts. Analytics are descriptive summaries of recorded
attendance and marks; the upcoming exam value and dashboard recent-activity
items are placeholders.

## Verify

With the backend running, `/api/health` should return `{"status":"ok"}`.
`/api/auth/me`, `/api/students/me`, and `/api/dashboard` require a valid
authenticated session and return 401 when signed out. The faculty management
routes likewise require a faculty session. Run backend tests from `backend`
with `python -m pytest`; build the frontend from `frontend` with
`npm run build`.
