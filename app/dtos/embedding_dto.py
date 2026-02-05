from typing import Any, Dict, List
from pydantic import BaseModel


class EmbeddingRequest(BaseModel):
    report: Dict[str, Any]


class ProjectEmbeddingRequest(BaseModel):
    text: str


class EmbeddingResponse(BaseModel):
    vector: List[float]
    dimension: int
