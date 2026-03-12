"""
Servicio RAG (Retrieval-Augmented Generation).
Pipeline: consulta → embeddings → búsqueda vectorial + metadata → contexto → Claude → respuesta con citas
"""
import uuid
import json
from typing import Optional, List
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger()

RAG_SYSTEM_PROMPT = """Eres PathOS, un asistente RAG clínico especializado para patólogos.
Tienes acceso a un repositorio de informes de patología, biopsias, citologías y resultados de laboratorio.

REGLAS ABSOLUTAS:
1. NUNCA inventes datos clínicos, diagnósticos, valores de laboratorio o información de pacientes.
2. SOLO usa información que aparezca explícitamente en el contexto de documentos proporcionado.
3. SIEMPRE cita el case_id y la fecha del documento fuente al final de cada afirmación relevante.
4. NUNCA mezcles información de pacientes distintos en una misma respuesta.
5. Si la información solicitada no está en el repositorio, dilo explícitamente: "No encontré ese dato en el repositorio."
6. Si la identidad del paciente es ambigua, solicita aclaración antes de responder.
7. Eres una herramienta de apoyo clínico interno. No reemplazas el criterio del patólogo.
8. Responde en español, de forma precisa, estructurada y profesional.
9. Indica nivel de confianza cuando corresponda (alto/medio/bajo).
10. Para casos críticos o urgentes, resáltalos explícitamente.

FORMATO DE CITAS: Al citar un documento, usa: [Fuente: {case_id} — {fecha}]
"""


def build_context_from_documents(documents: list) -> str:
    """Construye el bloque de contexto para el prompt RAG."""
    if not documents:
        return "REPOSITORIO VACÍO — No hay documentos disponibles para esta consulta."

    parts = ["=== DOCUMENTOS DEL REPOSITORIO ===\n"]
    for i, doc in enumerate(documents, 1):
        parts.append(f"""
--- Documento {i} ---
case_id: {doc.get('case_id', 'N/A')}
patient_id: {doc.get('patient_id', 'N/A')}
type: {doc.get('document_type', 'N/A')}
organ: {doc.get('organ_system', 'N/A')}
malignancy: {doc.get('malignancy', 'N/A')}
priority: {doc.get('priority', 'N/A')}
status: {doc.get('status', 'N/A')}
study_date: {doc.get('study_date', 'N/A')}
author: {doc.get('author', 'N/A')}
stain: {doc.get('stain_type', 'N/A')}
biomarker: {doc.get('biomarker', 'N/A')}
followup_required: {doc.get('followup_required', False)}
diagnosis_summary: {doc.get('diagnosis_summary', 'N/A')}
text_excerpt: {(doc.get('raw_text') or '')[:800]}
""")
    return "\n".join(parts)


async def rag_query(
    message: str,
    history: List[dict],
    anthropic_client,
    documents: list,
    patient_id: Optional[str] = None,
    case_id: Optional[str] = None,
) -> dict:
    """
    Ejecuta una consulta RAG completa.
    1. Filtra documentos por patient_id / case_id si se especifica
    2. Construye contexto
    3. Llama a Claude con historial
    4. Extrae case_ids citados en la respuesta
    """
    # Filtrar contexto si se especifica paciente/caso
    filtered_docs = documents
    if patient_id:
        filtered_docs = [d for d in documents if d.get("patient_id") == patient_id]
    if case_id:
        filtered_docs = [d for d in documents if d.get("case_id") == case_id]

    context = build_context_from_documents(filtered_docs)

    # Construir system prompt con contexto
    system = f"{RAG_SYSTEM_PROMPT}\n\n{context}"

    # Construir historial de mensajes
    messages = []
    for h in history[-10:]:  # últimos 10 turnos max
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1200,
            system=system,
            messages=messages,
        )
        answer = response.content[0].text

        # Extraer case_ids citados
        cited = [doc["case_id"] for doc in filtered_docs if doc.get("case_id") and doc["case_id"] in answer]

        return {
            "response": answer,
            "cited_documents": cited,
            "session_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "documents_searched": len(filtered_docs),
        }

    except Exception as e:
        logger.error("RAG query failed", error=str(e))
        return {
            "response": f"Error del sistema RAG: {str(e)}. Por favor intenta de nuevo.",
            "cited_documents": [],
            "session_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "documents_searched": 0,
        }


async def embed_text(text: str, model_name: str = "sentence-transformers/all-mpnet-base-v2") -> list:
    """
    Genera embedding vectorial para un texto.
    En producción: sentence-transformers o OpenAI embeddings.
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except ImportError:
        logger.warning("sentence-transformers no disponible — usando embedding mock")
        import random
        return [random.gauss(0, 0.1) for _ in range(768)]


def cosine_similarity(a: list, b: list) -> float:
    """Similitud coseno entre dos vectores."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def hybrid_search(query: str, documents: list, filters: dict = None, top_k: int = 10) -> list:
    """
    Búsqueda híbrida: keyword matching + filtros de metadata.
    En producción: añadir búsqueda vectorial con pgvector.
    """
    results = documents

    # Filtros de metadata
    if filters:
        if filters.get("organ_system"):
            results = [d for d in results if d.get("organ_system") == filters["organ_system"]]
        if filters.get("malignancy"):
            results = [d for d in results if d.get("malignancy") == filters["malignancy"]]
        if filters.get("status"):
            results = [d for d in results if d.get("status") == filters["status"]]
        if filters.get("priority"):
            results = [d for d in results if d.get("priority") == filters["priority"]]
        if filters.get("patient_id"):
            results = [d for d in results if d.get("patient_id") == filters["patient_id"]]

    # Keyword search en campos clave
    if query:
        q = query.lower()
        scored = []
        for doc in results:
            score = 0.0
            searchable = " ".join(str(v) for v in doc.values() if v).lower()
            # Score por matches
            score += searchable.count(q) * 0.3
            if q in (doc.get("case_id") or "").lower(): score += 2.0
            if q in (doc.get("patient_id") or "").lower(): score += 2.0
            if q in (doc.get("diagnosis_summary") or "").lower(): score += 1.5
            if q in (doc.get("organ_system") or "").lower(): score += 1.0
            if score > 0:
                scored.append((doc, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [{"document": d, "score": s, "matched_excerpt": None} for d, s in scored[:top_k]]

    return [{"document": d, "score": 1.0, "matched_excerpt": None} for d in results[:top_k]]
