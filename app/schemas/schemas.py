from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from datetime import datetime, date


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    facility: Optional[str]
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    role: Literal["admin", "pathologist", "viewer"] = "pathologist"
    facility: Optional[str] = None


# ─── Documents ────────────────────────────────────────────────────────────────

class DocumentFilters(BaseModel):
    patient_id: Optional[str] = None
    case_id: Optional[str] = None
    document_type: Optional[str] = None
    organ_system: Optional[str] = None
    malignancy: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    query: Optional[str] = None          # texto libre
    page: int = 1
    page_size: int = 20


class DocumentTagsIn(BaseModel):
    """Tags que el usuario puede editar manualmente tras la ingestión."""
    document_type: Optional[str] = None
    organ_system: Optional[str] = None
    malignancy: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    stain_type: Optional[str] = None
    biomarker: Optional[str] = None
    diagnosis_summary: Optional[str] = None
    followup_required: Optional[bool] = None
    tags: Optional[List[str]] = None


class DocumentOut(BaseModel):
    id: str
    case_id: str
    patient_id: str
    specimen_id: Optional[str]
    filename: str
    file_size_bytes: Optional[int]
    page_count: Optional[int]
    document_type: str
    status: str
    sensitivity: str
    organ_system: Optional[str]
    malignancy: Optional[str]
    priority: str
    stain_type: Optional[str]
    biomarker: Optional[str]
    diagnosis_summary: Optional[str]
    followup_required: bool
    study_date: Optional[date]
    received_date: Optional[date]
    ocr_applied: bool
    ocr_confidence: Optional[float]
    contains_phi: bool
    tags: List[str]
    facility: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: List[DocumentOut]
    total: int
    page: int
    page_size: int
    pages: int


# ─── Search ───────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    filters: Optional[DocumentFilters] = None
    top_k: int = Field(default=10, le=50)
    use_vector: bool = True


class SearchResult(BaseModel):
    document: DocumentOut
    score: float
    matched_excerpt: Optional[str]


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    query: str


# ─── Chat RAG ─────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []
    patient_id: Optional[str] = None     # acotar contexto a un paciente
    case_id: Optional[str] = None        # acotar contexto a un caso


class ChatResponse(BaseModel):
    response: str
    cited_documents: List[str]           # case_ids citados
    session_id: str
    timestamp: datetime


# ─── Audit ────────────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: str
    user_email: Optional[str]
    user_role: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    resource_name: Optional[str]
    ip_address: Optional[str]
    device_hint: Optional[str]
    status: str
    timestamp: datetime

    class Config:
        from_attributes = True


class AuditListResponse(BaseModel):
    items: List[AuditLogOut]
    total: int
    alerts: int
