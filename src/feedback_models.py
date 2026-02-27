from pydantic import BaseModel, Field


class FeedbackPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    response: str = Field(min_length=1, max_length=16000)
    rating: int = Field(
        ge=-1,
        le=1,
        description="Use 1 for thumbs up, -1 for thumbs down, 0 for neutral",
    )
    skill: str | None = Field(default=None, description="Optional skill id associated with the response")
    metadata: dict | None = Field(default=None, description="Optional additional client metadata")
