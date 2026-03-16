import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.db.database import Base
from app.core.config import settings


class DocumentEmbedding(Base):
    """
    Almacena el embedding vectorial de cada documento para búsqueda semántica.
    Usa pgvector para búsqueda por similitud coseno.
    """
    __tablename__ = "document_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # El embedding en sí (dimensión configurable vía settings)
    embedding: Mapped[list] = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=False)

    # Texto normalizado que se embeddó (para debugging y reindexación)
    embedded_text: Mapped[str] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)   # para chunking futuro

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    document: Mapped["Document"] = relationship("Document", back_populates="embedding")  # noqa

    def __repr__(self):
        return f"<Embedding doc={self.document_id} model={self.embedding_model}>"
