import uuid
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.db.database import get_db
from app.models.document import Document
from app.core.security import get_current_user
from app.schemas.schemas import DocumentOut, DocumentListResponse, DocumentTagsIn
from app.services import ingest_service, storage_service
from app.services.audit_service import log_event
from app.core.config import settings
import anthropic

router = APIRouter(prefix="/documents", tags=["Documents"])


def get_anthropic():
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    case_id: Optional[str] = Form(None),
    study_date: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Endpoint de ingestión completo:
    1. Valida el archivo
    2. Extrae texto (+ OCR si es necesario)
    3. Detecta PHI
    4. Llama a Claude para auto-tagging
    5. Sube a S3 cifrado
    6. Indexa en PostgreSQL
    7. Registra en auditoría
    """
    # Validar tamaño
    content = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Archivo muy grande. Máximo {settings.MAX_FILE_SIZE_MB}MB")

    # Validar tipo
    allowed_types = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"}
    if file.content_type not in allowed_types and not file.filename.endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(status_code=415, detail="Tipo de archivo no permitido. Usa PDF, DOCX o TXT.")

    # Extraer texto
    raw_text, page_count, ocr_applied = ingest_service.extract_text_from_pdf(content)
    checksum = ingest_service.compute_checksum(content)

    # Detectar PHI
    phi_entities = ingest_service.detect_phi(raw_text) if settings.ENABLE_PHI_DETECTION else {}
    contains_phi = bool(phi_entities)

    # Auto-tagging con Claude
    tags_data = {}
    if settings.ENABLE_AUTO_TAGGING:
        try:
            client = get_anthropic()
            tags_data = await ingest_service.auto_tag_with_claude(file.filename, raw_text[:3000], client)
        except Exception:
            tags_data = ingest_service._fallback_tags(file.filename)

    # Generar case_id si no se proporcionó
    resolved_case_id = case_id or ingest_service.generate_case_id(
        tags_data.get("document_type", "pathology_report"),
        datetime.now().year
    )

    # Subir a S3
    s3_key = storage_service.build_s3_key(
        tags_data.get("document_type", "pathology_report"),
        patient_id, resolved_case_id, file.filename
    )
    try:
        s3_result = await storage_service.upload_document(content, s3_key, file.content_type or "application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error subiendo a storage: {str(e)}")

    # Parsear fecha
    parsed_date = None
    if study_date:
        try:
            parsed_date = date.fromisoformat(study_date)
        except ValueError:
            pass

    # Guardar en base de datos
    doc = Document(
        id=str(uuid.uuid4()),
        case_id=resolved_case_id,
        patient_id=patient_id,
        filename=file.filename,
        s3_key=s3_key,
        s3_bucket=s3_result["bucket"],
        file_size_bytes=len(content),
        page_count=page_count,
        checksum_sha256=checksum,
        mime_type=file.content_type or "application/pdf",
        document_type=tags_data.get("document_type", "pathology_report"),
        status=tags_data.get("status", "draft"),
        sensitivity=tags_data.get("sensitivity", "PHI"),
        retention_class=tags_data.get("retention_class", "7-years-clinical"),
        organ_system=tags_data.get("organ_system"),
        malignancy=tags_data.get("malignancy"),
        priority=tags_data.get("priority", "routine"),
        stain_type=tags_data.get("stain_type"),
        biomarker=tags_data.get("biomarker"),
        diagnosis_summary=tags_data.get("diagnosis_summary"),
        followup_required=tags_data.get("followup_required", False),
        ocr_applied=ocr_applied,
        ocr_confidence=tags_data.get("ocr_confidence"),
        contains_phi=contains_phi,
        phi_entities=phi_entities,
        raw_text=raw_text[:50000],  # guardar hasta 50k chars
        language=tags_data.get("language", "es"),
        tags=tags_data.get("tags", []),
        study_date=parsed_date,
        author_id=current_user["user_id"],
        facility=None,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Auditoría
    ip = request.client.host if request.client else "unknown"
    await log_event(
        db, action="DOCUMENT_INGEST",
        user_id=current_user["user_id"], user_email=current_user["user_id"],
        user_role=current_user["role"],
        resource_type="document", resource_id=doc.id, resource_name=file.filename,
        detail=f"case_id={resolved_case_id}, phi={contains_phi}, ocr={ocr_applied}",
        ip_address=ip,
    )

    return doc


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    patient_id: Optional[str] = Query(None),
    organ_system: Optional[str] = Query(None),
    malignancy: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    stmt = select(Document)

    if patient_id: stmt = stmt.where(Document.patient_id == patient_id)
    if organ_system: stmt = stmt.where(Document.organ_system == organ_system)
    if malignancy: stmt = stmt.where(Document.malignancy == malignancy)
    if status: stmt = stmt.where(Document.status == status)
    if priority: stmt = stmt.where(Document.priority == priority)
    if document_type: stmt = stmt.where(Document.document_type == document_type)
    if query:
        q = f"%{query}%"
        stmt = stmt.where(
            or_(Document.case_id.ilike(q), Document.patient_id.ilike(q),
                Document.diagnosis_summary.ilike(q), Document.filename.ilike(q))
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    docs = result.scalars().all()

    return DocumentListResponse(
        items=docs, total=total, page=page,
        page_size=page_size, pages=-(-total // page_size)
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    ip = request.client.host if request.client else "unknown"
    await log_event(
        db, action="DOCUMENT_VIEW",
        user_id=current_user["user_id"], user_email=current_user["user_id"],
        user_role=current_user["role"],
        resource_type="document", resource_id=doc.id, resource_name=doc.filename,
        ip_address=ip,
    )
    return doc


@router.get("/{document_id}/download-url")
async def get_download_url(
    document_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retorna una URL pre-firmada de S3 válida por 5 minutos."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    try:
        url = storage_service.generate_presigned_url(doc.s3_key, expires_seconds=300, bucket=doc.s3_bucket)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando URL: {str(e)}")

    ip = request.client.host if request.client else "unknown"
    await log_event(
        db, action="DOCUMENT_DOWNLOAD",
        user_id=current_user["user_id"], user_email=current_user["user_id"],
        resource_type="document", resource_id=doc.id, resource_name=doc.filename,
        ip_address=ip,
    )
    return {"url": url, "expires_in": 300}


@router.patch("/{document_id}/tags", response_model=DocumentOut)
async def update_tags(
    document_id: str,
    body: DocumentTagsIn,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Permite al patólogo corregir o enriquecer los tags automáticos."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(doc, field, value)

    await db.commit()
    await db.refresh(doc)

    await log_event(
        db, action="DOCUMENT_TAGGED",
        user_id=current_user["user_id"], user_email=current_user["user_id"],
        resource_type="document", resource_id=doc.id, resource_name=doc.filename,
        detail=str(update_data),
    )
    return doc


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Solo admins pueden eliminar documentos."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar documentos")

    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    await storage_service.delete_document(doc.s3_key, doc.s3_bucket)
    await db.delete(doc)
    await db.commit()

    await log_event(
        db, action="DOCUMENT_DELETE",
        user_id=current_user["user_id"], user_email=current_user["user_id"],
        resource_type="document", resource_id=document_id, resource_name=doc.filename,
    )
