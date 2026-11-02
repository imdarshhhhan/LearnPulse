from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class AssignHomeworkSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    activityType: Literal["quiz", "homework"] = "quiz"
    materialId: int
    dueDate: date
    availableFrom: datetime | None = None
    studentIds: list[int] = Field(default_factory=list)
    groupIds: list[int] = Field(default_factory=list)
    classIds: list[int] = Field(default_factory=list)
    timeLimitMinutes: int | None = Field(default=None, ge=1, le=360)
    maxAttempts: int = Field(default=1, ge=1, le=10)
    randomizeQuestions: bool = True
    randomizeOptions: bool = True
    poolQuestionCount: int | None = Field(default=None, ge=1, le=100)
