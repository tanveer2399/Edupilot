# Day 5 — EduPilot AI Engineering Lab

## Descriptive analytics

EduPilot's dashboard calculates descriptive summaries from its existing
attendance and marks database records. The current sample data has 8 attendance
records and 4 mark assessments for one student:

- Attendance: 6 of 8 classes attended; `present` and `late` both count as
  attended, giving 75%.
- Marks: 99 points earned out of 115 possible, giving a weighted average of
  86.09%.
- Subject analytics can group attendance and marks by the existing `subject`
  field. Missing attendance or marks are represented as no data, not as zero.

These are summaries of recorded facts. They are not predictions.

## Python data-preparation concepts

- A database record is one stored row. A pandas DataFrame is an in-memory
  table that can be filtered, grouped, and calculated.
- A feature is an input value; a target is the outcome a supervised model
  would learn to estimate.
- The standalone `data_preparation_exercise.py` uses representative,
  clearly-labeled sample rows and the existing model field names. It groups
  attendance and marks by subject, demonstrates weighted and unweighted
  averages, and uses `NaN`, `isna`, and `dropna` to identify and exclude a
  practice-only missing mark rather than replacing it with zero.
- Its calculations produced 75% attendance and 86.09% weighted marks, matching
  the live dashboard values for the corresponding sample records. The simple
  mean of the four assessment percentages was 86.75%, illustrating why that
  mean differs from the dashboard's weighted result.

## Supervised-learning exercise

The standalone `synthetic_ml_exercise.py` generates 120 deterministic
synthetic examples. Attendance percentage and study hours are features; an
artificial exam score is the target. It reserves 25% (30 examples) for testing,
fits a linear regression model on the other 90 examples, and evaluates held-out
estimates:

- Mean absolute error: 3.86 synthetic score points.
- R-squared: 0.823 on this synthetic test split.

The target is generated from a formula with added random noise. The scores
describe only this artificial dataset and must not be interpreted as evidence
about real student performance.

## Limitations and environment

The current EduPilot data is far too small for reliable student-performance
modeling: 8 attendance rows and 4 marks rows belong to one sample student, and
they do not provide historical target outcomes across many independent
students. A tiny train/test split would not provide a trustworthy evaluation.

Pandas, NumPy, and scikit-learn are available in the separate system Python
3.11 environment used to run the learning exercises. They are not installed in
the backend virtual environment and were not added to `requirements.txt`.
Neither educational script connects to SQLAlchemy, the production API, or the
EduPilot database.

## Day 5 verification

- Backend regression suite: 41 tests passed; one existing
  Starlette/httpx deprecation warning was reported.
- Frontend production build: passed.
- Both standalone learning scripts ran successfully.
- Live core GET API routes for health, student, dashboard, attendance,
  attendance summary, marks, assignments, and timetable returned successful
  responses during verification.
- Browser smoke checks rendered Dashboard, Attendance, Marks, Assignments,
  Timetable, Study Assistant, and Study Planner. Assignment details loaded,
  the Study Assistant returned a real Ollama response, and the quiz workflow
  generated five questions and displayed a backend-scored submission result.
- A Git change list could not be produced: the supplied workspace directory
  does not contain a `.git` repository.
