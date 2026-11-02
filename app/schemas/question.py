from pydantic import BaseModel, Field
from typing import List

class RequestQuestionSchema(BaseModel):
    conceptTag: str

class SubmitAnswerSchema(BaseModel):
    questionId: int = Field(..., gt=0)
    chosenOption: str = Field(..., min_length=1, max_length=1000)
    conceptTag: str = Field(..., min_length=1, max_length=120)
    submissionId: str | None = Field(
        default=None,
        min_length=16,
        max_length=64,
        pattern=r"^[A-Za-z0-9-]+$",
    )
