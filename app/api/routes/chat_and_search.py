"""
Rutas de Chat RAG y Búsqueda Híbrida.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anthropic

from app.db.database import get_db
from app.models.document import Document
from app.core.security import get_current_user
from app.schemas.schemas import ChatRequest, ChatResponse, SearchRequest, SearchResponse
from app.services.rag_service import rag_query, hybrid_search
from app.services.audit_service import log_event
from app.core.config import settings

chat_router = APIRouter(prefix="/chat", tags=["Chat RAG"])
search_router = APIRouter(prefix="/search", tags=["Search"])


def get_anthropic():
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def doc_to_dict(doc: Document) -> dict:
    return {
        "id": doc.id,
        "case_id": doc.case_id,
        "patient_id": doc.patient_id,
        "document_type": doc.document_type,
        "organ_system": doc.organ_system,
        "malignancy": doc.malignancy,
        "priority": doc.priority,
        "status": doc.status,
        "stain_type": doc.stain_type,
        "biomarker": doc.biomarker,
        "diagnosis_summary": doc.diagnosis_summary,
        "followup_required": doc.followup_required,
        "study_date": str(doc.study_date) if doc.study_date else None,
        "raw_text": doc.raw_text,
        "tags": doc.tags or [],
        "author": doc.author_id,
        "filename": doc.filename,
    }


@chat_router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Endpoint RAG: recibe consulta en lenguaje natural,
    recupera documentos relevantes e invoca Claude con contexto.
    """
    # Cargar documentos del repositorio
    stmt = select(Document)
    if body.patient_id:
        stmt = stmt.where(Document.patient_id == body.patient_id)
    if body.case_id:
        stmt = stmt.where(Document.case_id == body.case_id)

    result = await db.execute(stmt.limit(50))  # máx 50 docs en contexto
    documents = [doc_to_dict(d) for d in result.scalars().all()]

    # Ejecutar RAG
    client = get_anthropic()
    history = [{"role": m.role, "content": m.content} for m in (body.history or [])]

    rag_result = await rag_query(
        message=body.message,
        history=history,
        anthropic_client=client,
        documents=documents,
        patient_id=body.patient_id,
        case_id=body.case_id,
    )

    # Auditoría
    ip = request.client.host if request.client else "unknown"
    await log_event(
        db, action="RAG_QUERY",
        user_id=current_user["user_id"], user_email=current_user["user_id"],
        user_role=current_user["role"],
        resource_type="chat", resource_name=body.message[:100],
        detail=f"docs_searched={rag_result['documents_searched']}, cited={rag_result['cited_documents']}",
        ip_address=ip,
    )

    return ChatResponse(
        response=rag_result["response"],
        cited_documents=rag_result["cited_documents"],
        session_id=rag_result["session_id"],
        timestamp=rag_result["timestamp"],
    )


@search_router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Búsqueda híbrida: keyword + filtros de metadata + (opcional) vector similarity.
    """
    stmt = select(Document)
    result = await db.execute(stmt.limit(500))
    all_docs = [doc_to_dict(d) for d in result.scalars().all()]

    filters = {}
    if body.filters:
        f = body.filters
        if f.organ_system: filters["organ_system"] = f.organ_system
        if f.malignancy: filters["malignancy"] = f.malignancy
        if f.status: filters["status"] = f.status
        if f.priority: filters["priority"] = f.priority
        if f.patient_id: filters["patient_id"] = f.patient_id

    search_results = hybrid_search(body.query, all_docs, filters=filters, top_k=body.top_k)

    ip = request.client.host if request.client else "unknown"
    await log_event(
        db, action="SEARCH_QUERY",
        user_id=current_user["user_id"], user_email=current_user["user_id"],
        resource_name=body.query[:100], detail=f"results={len(search_results)}",
        ip_address=ip,
    )

    # Formatear para el schema de respuesta
    formatted = []
    for r in search_results:
        doc_data = r["document"]
        # Convertir dict a objeto para el schema
        from app.schemas.schemas import DocumentOut
        try:
            doc_out = DocumentOut(**{k: v for k, v in doc_data.items() if k in DocumentOut.model_fields})
        except Exception:
            continue
        formatted.append({"document": doc_out, "score": r["score"], "matched_excerpt": r.get("matched_excerpt")})

    return SearchResponse(results=formatted, total=len(formatted), query=body.query)
