from typing import Any
from pydantic import BaseModel


class EmbeddingRequest(BaseModel):
    report: dict[str, Any]


class ProjectEmbeddingRequest(BaseModel):
    text: str


class EmbeddingResponse(BaseModel):
    vector: list[float]
    dimension: int
