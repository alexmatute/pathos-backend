import uuid
from datetime import datetime, timezone, date
from sqlalchemy import (
    String, Boolean, DateTime, Date, Float, Text,
    ForeignKey, Enum as SAEnum, JSON, Integer
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    patient_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    specimen_id: Mapped[str] = mapped_column(String(100), nullable=True)

    # ── File metadata ─────────────────────────────────────────────────────────
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)         # ruta en S3
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), default="application/pdf")

    # ── Clinical tags (obligatorios) ──────────────────────────────────────────
    document_type: Mapped[str] = mapped_column(
        SAEnum("pathology_report", "biopsy", "cytology", "immunohistochemistry",
               "lab_result", "consent", "image_note", name="doc_type"),
        nullable=False, default="pathology_report"
    )
    status: Mapped[str] = mapped_column(
        SAEnum("draft", "final", "amended", name="doc_status"),
        nullable=False, default="draft"
    )
    sensitivity: Mapped[str] = mapped_column(
        SAEnum("PHI", "de-identified", "restricted", name="doc_sensitivity"),
        nullable=False, default="PHI"
    )
    retention_class: Mapped[str] = mapped_column(String(64), default="7-years-clinical")

    # ── Clinical tags (clínicos opcionales) ──────────────────────────────────
    organ_system: Mapped[str] = mapped_column(
        SAEnum("breast", "colon", "prostate", "skin", "lung", "liver",
               "kidney", "thyroid", "brain", "bladder", "other", name="organ_system"),
        nullable=True
    )
    malignancy: Mapped[str] = mapped_column(
        SAEnum("benign", "suspicious", "malignant", "undetermined", name="malignancy"),
        nullable=True
    )
    priority: Mapped[str] = mapped_column(
        SAEnum("routine", "urgent", "critical", name="priority"),
        default="routine"
    )
    stain_type: Mapped[str] = mapped_column(String(128), nullable=True)        # H&E, IHC, etc.
    biomarker: Mapped[str] = mapped_column(String(255), nullable=True)
    diagnosis_code: Mapped[str] = mapped_column(String(32), nullable=True)     # ICD-10
    diagnosis_summary: Mapped[str] = mapped_column(Text, nullable=True)
    followup_required: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Dates ─────────────────────────────────────────────────────────────────
    study_date: Mapped[date] = mapped_column(Date, nullable=True)
    received_date: Mapped[date] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Processing metadata ───────────────────────────────────────────────────
    ocr_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    contains_phi: Mapped[bool] = mapped_column(Boolean, default=True)
    phi_entities: Mapped[dict] = mapped_column(JSON, nullable=True)            # PHI encontrada
    raw_text: Mapped[str] = mapped_column(Text, nullable=True)                 # texto extraído
    language: Mapped[str] = mapped_column(String(10), default="es")
    tags: Mapped[list] = mapped_column(JSON, default=list)                     # tags libres

    # ── Author + Facility ─────────────────────────────────────────────────────
    author_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    facility: Mapped[str] = mapped_column(String(255), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    author: Mapped["User"] = relationship("User", back_populates="documents")  # noqa
    embedding: Mapped["DocumentEmbedding"] = relationship(  # noqa
        "DocumentEmbedding", back_populates="document", uselist=False
    )

    def __repr__(self):
        return f"<Document {self.case_id} [{self.document_type}]>"

    # Relación con AuditLog (viewonly — trazabilidad de accesos al documento)
    # audit_logs: ver audit_log.py para la relación inversa
