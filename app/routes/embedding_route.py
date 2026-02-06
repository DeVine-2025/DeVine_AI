from fastapi import APIRouter
from app.dtos.request_dto import EmbeddingReq, ProjectEmbeddingReq
from app.dtos.response_dto import EmbeddingRes
from app.controllers.embedding_controller import embedding_controller

router = APIRouter()


@router.post("/report", response_model=EmbeddingRes)
async def embed_report(request: EmbeddingReq):
    """리포트 임베딩: POST /api/v1/embeddings/report"""
    return await embedding_controller.embed_report(request)


@router.post("/project", response_model=EmbeddingRes)
async def embed_project(request: ProjectEmbeddingReq):
    """프로젝트 임베딩: POST /api/v1/embeddings/project"""
    return await embedding_controller.embed_project(request)
