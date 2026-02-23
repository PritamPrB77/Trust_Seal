from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    shipment_id: Optional[str] = Field(default=None, max_length=128)


class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"
