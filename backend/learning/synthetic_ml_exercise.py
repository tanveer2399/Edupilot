import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


print("EDUCATIONAL EXERCISE: synthetic examples only; not real student data")

rng = np.random.default_rng(seed=7)
synthetic_attendance = rng.uniform(50, 100, size=120)
synthetic_study_hours = rng.uniform(0, 10, size=120)
random_noise = rng.normal(0, 5, size=120)
synthetic_exam_score = np.clip(
    25 + 0.5 * synthetic_attendance + 3 * synthetic_study_hours + random_noise,
    0,
    100,
)

features = np.column_stack((synthetic_attendance, synthetic_study_hours))
target = synthetic_exam_score
print(f"Generated synthetic examples: {len(target)}")
print("Feature columns: attendance_percentage, study_hours")
print("Target column: synthetic_exam_score")

features_train, features_test, target_train, target_test = train_test_split(
    features,
    target,
    test_size=0.25,
    random_state=42,
)
print(f"Training examples: {len(target_train)}")
print(f"Testing examples held aside: {len(target_test)}")

model = LinearRegression()
model.fit(features_train, target_train)
predicted_test_scores = model.predict(features_test)

mae = mean_absolute_error(target_test, predicted_test_scores)
r_squared = r2_score(target_test, predicted_test_scores)
print(f"Mean absolute error on synthetic test data: {mae:.2f} score points")
print(f"R-squared on synthetic test data: {r_squared:.3f}")

print("\nFirst five held-out synthetic examples:")
for actual_score, predicted_score in zip(
    target_test[:5],
    predicted_test_scores[:5],
    strict=True,
):
    print(
        f"synthetic actual={actual_score:.1f}, "
        f"synthetic estimate={predicted_score:.1f}"
    )

print(
    "\nThese metrics describe only this generated dataset; "
    "they are not evidence about real student performance."
)
