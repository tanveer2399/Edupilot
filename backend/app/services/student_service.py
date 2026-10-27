from sqlalchemy.orm import Session

from app.models import Student

SAMPLE_STUDENT = {
    "student_id": "STU-2024-0186",
    "full_name": "Tanveer",
    "email": "aarav.sharma@example.edu",
    "department": "Computer Science",
    "semester": 4,
    "is_demo": True,
}


def ensure_sample_student(db: Session) -> Student:
    student = db.get(Student, SAMPLE_STUDENT["student_id"])
    if student is None:
        student = Student(**SAMPLE_STUDENT)
        db.add(student)
    else:
        for field, value in SAMPLE_STUDENT.items():
            if getattr(student, field) != value:
                setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return student
