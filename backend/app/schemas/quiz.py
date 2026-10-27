from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


Difficulty = Literal["easy", "medium", "hard"]
OptionId = Literal["A", "B", "C", "D"]


class QuizGenerateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    topic: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=10000)
    num_questions: Literal[5, 10, 15] = 5
    difficulty: Difficulty = "easy"

    @model_validator(mode="after")
    def require_topic_or_notes(self):
        if not self.topic and not self.notes:
            raise ValueError("Provide a topic or study notes to generate a quiz.")
        return self


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", str_strip_whitespace=True)

    question_id: str = Field(min_length=1, max_length=40)
    question: str = Field(min_length=1, max_length=1000)
    options: dict[OptionId, str]
    correct_answer: OptionId
    explanation: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_options(self):
        if set(self.options) != {"A", "B", "C", "D"}:
            raise ValueError("Each quiz question must have options A, B, C, and D.")
        option_texts = [value.strip().casefold() for value in self.options.values()]
        if len(set(option_texts)) != 4:
            raise ValueError("Each quiz question must have four distinct options.")
        return self


class GeneratedQuiz(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    questions: list[GeneratedQuestion]


class QuizQuestionResponse(BaseModel):
    question_id: str
    question: str
    options: dict[OptionId, str]


class QuizGenerateResponse(BaseModel):
    quiz_id: UUID
    topic: str | None
    num_questions: int
    difficulty: Difficulty
    questions: list[QuizQuestionResponse]


class QuizAnswer(BaseModel):
    question_id: str = Field(min_length=1, max_length=40)
    selected_answer: OptionId | None


class QuizSubmitRequest(BaseModel):
    answers: list[QuizAnswer] = Field(max_length=15)


class QuizQuestionResult(BaseModel):
    question_id: str
    question: str
    options: dict[OptionId, str]
    selected_answer: OptionId | None
    correct_answer: OptionId
    explanation: str
    is_correct: bool


class QuizSubmitResponse(BaseModel):
    quiz_id: UUID
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    score_percentage: float
    results: list[QuizQuestionResult]


class StudyPlanStep(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    focus: str = Field(min_length=3, max_length=160)
    activity: str = Field(min_length=5, max_length=500)
    minutes: int = Field(ge=5, le=20)


class GeneratedStudyPlan(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    steps: list[StudyPlanStep] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_total_duration(self):
        if sum(step.minutes for step in self.steps) > 60:
            raise ValueError("A study plan must take no more than 60 minutes.")
        return self


class StudyPlanResponse(BaseModel):
    quiz_id: UUID
    topic: str | None
    steps: list[StudyPlanStep]
