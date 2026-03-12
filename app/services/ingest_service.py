"""
Servicio de ingestión de documentos.
Pipeline: upload → extracción → OCR → PHI → tagging (Claude) → embeddings → indexación
"""
import re
import json
import hashlib
import uuid
from typing import Optional
from pathlib import Path
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# ─── PHI Patterns (HIPAA Safe Harbor identifiers) ────────────────────────────
PHI_PATTERNS = {
    "ssn":          r"\b\d{3}-\d{2}-\d{4}\b",
    "mrn":          r"\b(MRN|Medical Record)[:\s#]*\d{5,12}\b",
    "dob":          r"\b(DOB|Date of Birth|Fecha de Nacimiento)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    "phone":        r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
    "email":        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "zip":          r"\b\d{5}(-\d{4})?\b",
    "name_prefix":  r"\b(Patient|Paciente|Name|Nombre)[:\s]+[A-Z][a-z]+ [A-Z][a-z]+\b",
    "npi":          r"\b(NPI)[:\s#]*\d{10}\b",
    "account":      r"\b(Account|Cuenta|ID)[:\s#]*\d{6,12}\b",
}


def detect_phi(text: str) -> dict:
    """Detecta entidades PHI en el texto. Retorna dict con tipo → lista de matches."""
    found = {}
    for phi_type, pattern in PHI_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            found[phi_type] = [str(m) if isinstance(m, str) else m[0] for m in matches]
    return found


def redact_phi(text: str, placeholder: str = "[REDACTED]") -> str:
    """Reemplaza PHI detectada en el texto (para ambientes dev/testing)."""
    redacted = text
    for pattern in PHI_PATTERNS.values():
        redacted = re.sub(pattern, placeholder, redacted, flags=re.IGNORECASE)
    return redacted


def compute_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extract_text_from_pdf(content: bytes) -> tuple[str, int, bool]:
    """
    Extrae texto de un PDF.
    Retorna: (texto, num_páginas, ocr_aplicado)
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        pages = len(doc)
        text_parts = []
        ocr_needed = True

        for page in doc:
            page_text = page.get_text("text")
            if page_text.strip():
                ocr_needed = False
                text_parts.append(page_text)

        if ocr_needed and settings.ENABLE_OCR:
            logger.info("PDF sin texto embebido — aplicando OCR")
            text_parts, ocr_confidence = _apply_ocr(doc)
            return "\n\n".join(text_parts), pages, True

        return "\n\n".join(text_parts), pages, False
    except ImportError:
        logger.warning("PyMuPDF no disponible — texto mock")
        return "Texto extraído del documento (mock — instalar pymupdf)", 1, False
    except Exception as e:
        logger.error("Error extrayendo texto de PDF", error=str(e))
        return "", 0, False


def _apply_ocr(doc) -> tuple[list[str], float]:
    """Aplica OCR a páginas de un documento fitz."""
    try:
        import pytesseract
        from PIL import Image
        import io

        texts = []
        confidences = []
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            data = pytesseract.image_to_data(img, lang="spa+eng", output_type=pytesseract.Output.DICT)
            text = " ".join(w for w in data["text"] if w.strip())
            conf_vals = [c for c in data["conf"] if c > 0]
            confidences.extend(conf_vals)
            texts.append(text)

        avg_conf = sum(confidences) / len(confidences) / 100 if confidences else 0.0
        return texts, avg_conf
    except Exception as e:
        logger.error("OCR failed", error=str(e))
        return [], 0.0


async def auto_tag_with_claude(filename: str, text_excerpt: str, anthropic_client) -> dict:
    """
    Llama a Claude para asignar tags clínicos estructurados.
    Retorna JSON con metadatos del documento.
    """
    system = """Eres un sistema de clasificación clínica automatizado para un laboratorio de patología.
Tu única función es analizar documentos de patología y retornar metadatos clínicos en JSON estricto.
Responde SOLO con JSON válido. Sin texto adicional, sin backticks, sin comentarios."""

    prompt = f"""Analiza este fragmento de un documento clínico y clasifícalo.

Nombre del archivo: {filename}

Fragmento de texto:
{text_excerpt[:2000]}

Responde EXACTAMENTE con este JSON (todos los campos requeridos):
{{
  "document_type": "pathology_report|biopsy|cytology|immunohistochemistry|lab_result|consent|image_note",
  "organ_system": "breast|colon|prostate|skin|lung|liver|kidney|thyroid|brain|bladder|other",
  "malignancy": "malignant|suspicious|benign|undetermined",
  "priority": "critical|urgent|routine",
  "status": "draft|final|amended",
  "sensitivity": "PHI",
  "stain_type": "H&E|IHC|Papanicolaou|FISH|special|other|null",
  "biomarker": "string o null",
  "diagnosis_summary": "resumen clínico en 1-2 oraciones",
  "followup_required": true,
  "contains_phi": true,
  "ocr_confidence": 0.95,
  "retention_class": "7-years-clinical",
  "language": "es|en",
  "tags": ["lista", "de", "tags", "relevantes"]
}}"""

    try:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
            system=system,
        )
        raw = message.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Claude retornó JSON inválido", raw=raw[:200])
        return _fallback_tags(filename)
    except Exception as e:
        logger.error("Error llamando a Claude para tagging", error=str(e))
        return _fallback_tags(filename)


def _fallback_tags(filename: str) -> dict:
    """Tags por defecto si Claude falla."""
    name = filename.lower()
    return {
        "document_type": "pathology_report",
        "organ_system": next((o for o in ["breast","colon","lung","prostate","skin"] if o in name), "other"),
        "malignancy": "undetermined",
        "priority": "urgent" if "urgent" in name or "critical" in name else "routine",
        "status": "amended" if "amended" in name else "final" if "final" in name else "draft",
        "sensitivity": "PHI",
        "stain_type": "IHC" if "ihc" in name or "immuno" in name else "H&E",
        "biomarker": None,
        "diagnosis_summary": "Requiere revisión manual — clasificación automática no disponible.",
        "followup_required": True,
        "contains_phi": True,
        "ocr_confidence": 0.0,
        "retention_class": "7-years-clinical",
        "language": "es",
        "tags": ["pendiente-revision"],
    }


def generate_case_id(organ: str, year: int) -> str:
    """Genera un case_id único en formato BX-YYYY-XXXX."""
    suffix = str(uuid.uuid4().int)[:4].zfill(4)
    prefix = {"biopsy": "BX", "cytology": "CYT", "immunohistochemistry": "IHC"}.get(organ, "RPT")
    return f"{prefix}-{year}-{suffix}"
