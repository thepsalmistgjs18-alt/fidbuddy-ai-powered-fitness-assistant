from pydantic import BaseModel, Field


class UserInput(BaseModel):
    contact: str = Field(min_length=5, max_length=160)
    username: str = Field(min_length=1, max_length=100)
    age: int = Field(gt=0, lt=120)
    weight: float = Field(gt=0)
    goal: str = Field(min_length=1, max_length=200)
    intensity: str = Field(min_length=1, max_length=30)


class FeedbackRequest(BaseModel):
    feedback: str = Field(min_length=1, max_length=2000)