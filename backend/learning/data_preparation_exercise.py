import numpy as np
import pandas as pd


print("LEARNING EXERCISE: representative sample data, not a database export")
sample_student_id = "STU-2024-0186"

attendance_df = pd.DataFrame(
    [
        (sample_student_id, "Data Structures", "2026-10-05", "present"),
        (sample_student_id, "Database Systems", "2026-10-05", "present"),
        (sample_student_id, "Operating Systems", "2026-10-06", "absent"),
        (sample_student_id, "Computer Networks", "2026-10-07", "present"),
        (sample_student_id, "Data Structures", "2026-10-12", "late"),
        (sample_student_id, "Database Systems", "2026-10-12", "absent"),
        (sample_student_id, "Operating Systems", "2026-10-13", "present"),
        (sample_student_id, "Computer Networks", "2026-10-14", "present"),
    ],
    columns=["student_id", "subject", "class_date", "status"],
)

attendance_df["attended"] = attendance_df["status"].isin(["present", "late"])
attendance_by_subject = (
    attendance_df.groupby("subject", as_index=False)
    .agg(
        classes_attended=("attended", "sum"),
        total_classes=("status", "count"),
    )
)
attendance_by_subject["attendance_percentage"] = (
    attendance_by_subject["classes_attended"]
    / attendance_by_subject["total_classes"]
    * 100
).round(2)
print("\nSample attendance summary:")
print(attendance_by_subject.to_string(index=False))

marks_df = pd.DataFrame(
    [
        (
            sample_student_id,
            "Data Structures",
            "Quiz 1",
            18,
            20,
            "2026-10-08",
        ),
        (
            sample_student_id,
            "Database Systems",
            "Midterm",
            42,
            50,
            "2026-10-10",
        ),
        (
            sample_student_id,
            "Operating Systems",
            "Quiz 1",
            17,
            20,
            "2026-10-14",
        ),
        (
            sample_student_id,
            "Computer Networks",
            "Lab assessment",
            22,
            25,
            "2026-10-16",
        ),
    ],
    columns=[
        "student_id",
        "subject",
        "assessment_name",
        "marks_obtained",
        "maximum_marks",
        "assessment_date",
    ],
)

marks_df["assessment_percentage"] = (
    marks_df["marks_obtained"] / marks_df["maximum_marks"] * 100
).round(2)
marks_by_subject = (
    marks_df.groupby("subject", as_index=False)
    .agg(
        marks_earned=("marks_obtained", "sum"),
        marks_possible=("maximum_marks", "sum"),
        assessments_count=("assessment_name", "count"),
    )
)
marks_by_subject["marks_percentage"] = (
    marks_by_subject["marks_earned"] / marks_by_subject["marks_possible"] * 100
).round(2)
simple_mean = np.mean(marks_df["assessment_percentage"].to_numpy())
weighted_mean = np.average(
    marks_df["assessment_percentage"],
    weights=marks_df["maximum_marks"],
)
print("\nSample marks by subject:")
print(marks_by_subject.to_string(index=False))
print(f"\nSimple mean of assessment percentages: {simple_mean:.2f}%")
print(f"Weighted overall marks percentage: {weighted_mean:.2f}%")

missing_value_sample = pd.DataFrame(
    [
        ("Data Structures", "Quiz 1", 18, 20),
        ("Database Systems", "Assessment not recorded", np.nan, np.nan),
    ],
    columns=["subject", "assessment_name", "marks_obtained", "maximum_marks"],
)
missing_rows = missing_value_sample[
    missing_value_sample[["marks_obtained", "maximum_marks"]].isna().any(axis=1)
]
complete_rows = missing_value_sample.dropna(
    subset=["marks_obtained", "maximum_marks"]
).copy()
complete_rows["percentage"] = (
    complete_rows["marks_obtained"] / complete_rows["maximum_marks"] * 100
).round(2)
print("\nPractice-only row(s) with missing marks (NaN means not recorded):")
print(missing_rows.to_string(index=False))
print("\nPercentages from rows with recorded marks only:")
print(complete_rows[["subject", "percentage"]].to_string(index=False))
