from datetime import date, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.student import Student


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "subject",
            "class_date",
            name="uq_attendance_student_subject_date",
        ),
        CheckConstraint(
            "status IN ('present', 'absent', 'late')",
            name="ck_attendance_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    class_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    remarks: Mapped[str | None] = mapped_column(String(500))

    student: Mapped[Student] = relationship(back_populates="attendance_records")


class MarkRecord(Base):
    __tablename__ = "mark_records"
    __table_args__ = (
        CheckConstraint("marks_obtained >= 0", name="ck_marks_obtained_nonnegative"),
        CheckConstraint("maximum_marks > 0", name="ck_marks_maximum_positive"),
        CheckConstraint(
            "marks_obtained <= maximum_marks",
            name="ck_marks_obtained_within_maximum",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    assessment_name: Mapped[str] = mapped_column(String(160), nullable=False)
    marks_obtained: Mapped[float] = mapped_column(nullable=False)
    maximum_marks: Mapped[float] = mapped_column(nullable=False)
    assessment_date: Mapped[date | None] = mapped_column(Date)

    student: Mapped[Student] = relationship(back_populates="marks")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'submitted')",
            name="ck_assignment_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")

    student: Mapped[Student] = relationship(back_populates="assignments")


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"
    __table_args__ = (
        CheckConstraint(
            "day_of_week IN "
            "('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')",
            name="ck_timetable_day_of_week",
        ),
        CheckConstraint("end_time > start_time", name="ck_timetable_end_after_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))

    student: Mapped[Student] = relationship(back_populates="timetable_entries")
