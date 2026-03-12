import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class AuditLog(Base):
    """
    Registro de auditoría inmutable (append-only).
    NUNCA se actualiza ni se elimina — requerimiento HIPAA.
    """
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Quién
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=True)        # desnormalizado
    user_role: Mapped[str] = mapped_column(String(32), nullable=True)

    # Qué
    action: Mapped[str] = mapped_column(
        SAEnum(
            "LOGIN", "LOGIN_FAILED", "LOGOUT",
            "DOCUMENT_VIEW", "DOCUMENT_UPLOAD", "DOCUMENT_DELETE", "DOCUMENT_DOWNLOAD",
            "DOCUMENT_INGEST", "DOCUMENT_TAGGED",
            "RAG_QUERY", "RAG_RESPONSE",
            "SEARCH_QUERY",
            "USER_CREATED", "USER_UPDATED", "USER_DEACTIVATED",
            "EXPORT",
            name="audit_action"
        ),
        nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=True)      # document, user, etc.
    resource_id: Mapped[str] = mapped_column(String(255), nullable=True)       # ID del recurso
    resource_name: Mapped[str] = mapped_column(String(512), nullable=True)     # nombre legible
    detail: Mapped[str] = mapped_column(Text, nullable=True)                   # JSON o texto libre

    # Dónde / Cuándo
    ip_address: Mapped[str] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(512), nullable=True)
    device_hint: Mapped[str] = mapped_column(String(128), nullable=True)       # inferido del UA
    session_id: Mapped[str] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Estado del evento
    status: Mapped[str] = mapped_column(
        SAEnum("success", "failure", "alert", name="audit_status"),
        default="success"
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="audit_logs")  # noqa

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_email} at {self.timestamp}>"
