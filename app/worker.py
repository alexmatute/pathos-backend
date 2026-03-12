"""
PathOS — Celery Worker
Procesa tareas asíncronas: ingestión de PDFs, generación de embeddings,
detección de PHI, tagging con Claude y notificaciones.
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "pathos_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bogota",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "pathos.ingest": {"queue": "ingest"},
        "pathos.embed": {"queue": "embed"},
        "pathos.notify": {"queue": "notify"},
    },
)


@celery_app.task(name="pathos.ingest", bind=True, max_retries=3)
def task_ingest_document(self, document_id: str):
    """
    Pipeline completo de ingestión asíncrona:
    1. Descarga el archivo de GCS/S3
    2. Extrae texto (+ OCR si es necesario)
    3. Detecta PHI
    4. Auto-tagging con Claude
    5. Genera embeddings
    6. Actualiza la base de datos
    """
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.document import Document
    from app.services import ingest_service, storage_service
    import anthropic

    try:
        engine = create_engine(settings.DATABASE_URL_SYNC)
        Session = sessionmaker(bind=engine)

        with Session() as db:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                return {"status": "not_found", "document_id": document_id}

            # Descargar contenido
            content = asyncio.run(storage_service.get_document_content(doc.s3_key, doc.s3_bucket))

            # Extraer texto
            raw_text, page_count, ocr_applied = ingest_service.extract_text_from_pdf(content)

            # Detectar PHI
            phi_entities = ingest_service.detect_phi(raw_text) if settings.ENABLE_PHI_DETECTION else {}

            # Auto-tagging con Claude
            if settings.ENABLE_AUTO_TAGGING and not doc.diagnosis_summary:
                client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                tags = asyncio.run(ingest_service.auto_tag_with_claude(doc.filename, raw_text[:3000], client))
                doc.document_type = tags.get("document_type", doc.document_type)
                doc.organ_system = tags.get("organ_system", doc.organ_system)
                doc.malignancy = tags.get("malignancy", doc.malignancy)
                doc.priority = tags.get("priority", doc.priority)
                doc.diagnosis_summary = tags.get("diagnosis_summary", doc.diagnosis_summary)
                doc.stain_type = tags.get("stain_type", doc.stain_type)
                doc.followup_required = tags.get("followup_required", doc.followup_required)
                doc.tags = tags.get("tags", doc.tags or [])
                doc.language = tags.get("language", "es")

            # Actualizar doc
            doc.raw_text = raw_text[:50000]
            doc.page_count = page_count
            doc.ocr_applied = ocr_applied
            doc.contains_phi = bool(phi_entities)
            doc.phi_entities = phi_entities
            db.commit()

        return {"status": "completed", "document_id": document_id}

    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="pathos.embed", bind=True, max_retries=3)
def task_generate_embedding(self, document_id: str):
    """Genera y almacena el embedding vectorial del documento."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.document import Document
    from app.models.embedding import DocumentEmbedding
    from app.services.rag_service import embed_text
    import asyncio

    try:
        engine = create_engine(settings.DATABASE_URL_SYNC)
        Session = sessionmaker(bind=engine)

        with Session() as db:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc or not doc.raw_text:
                return {"status": "skipped", "reason": "no_text"}

            # Texto para embedding: diagnóstico + texto extraído
            text_to_embed = f"{doc.diagnosis_summary or ''}\n{doc.raw_text[:2000]}"
            vector = asyncio.run(embed_text(text_to_embed, settings.EMBEDDING_MODEL))

            existing = db.query(DocumentEmbedding).filter(DocumentEmbedding.document_id == document_id).first()
            if existing:
                existing.embedding = vector
                existing.embedded_text = text_to_embed[:1000]
            else:
                emb = DocumentEmbedding(
                    document_id=document_id,
                    embedding=vector,
                    embedded_text=text_to_embed[:1000],
                    embedding_model=settings.EMBEDDING_MODEL,
                )
                db.add(emb)
            db.commit()

        return {"status": "completed", "document_id": document_id}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(name="pathos.notify")
def task_send_alert(event_type: str, document_id: str, message: str = ""):
    """
    Dispara notificaciones a n8n cuando ocurre un evento clínico relevante.
    n8n se encarga de enviar email + Telegram.
    """
    import httpx
    try:
        payload = {
            "event_type": event_type,
            "document": {"id": document_id},
            "message": message,
        }
        httpx.post(
            f"{settings.APP_ENV and 'http://n8n:5678' or 'http://localhost:5678'}"
            "/webhook/pathos-notify-email",
            json=payload,
            timeout=10,
        )
    except Exception as e:
        import structlog
        structlog.get_logger().error("notify_failed", error=str(e))
