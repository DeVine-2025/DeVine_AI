from fastapi import APIRouter
from app.dtos.embedding_dto import EmbeddingRequest, ProjectEmbeddingRequest, EmbeddingResponse
from app.controllers.embedding_controller import embedding_controller

router = APIRouter()


@router.post("/report", response_model=EmbeddingResponse)
async def embed_report(request: EmbeddingRequest):
    """리포트 임베딩: POST /api/v1/embeddings/report"""
    return await embedding_controller.embed_report(request)


@router.post("/project", response_model=EmbeddingResponse)
async def embed_project(request: ProjectEmbeddingRequest):
    """프로젝트 임베딩: POST /api/v1/embeddings/project"""
    return await embedding_controller.embed_project(request)
