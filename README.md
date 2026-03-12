# PathOS Backend — Clinical RAG System

## Stack
- **Runtime**: Python 3.11+
- **Framework**: FastAPI
- **Database**: PostgreSQL 15 + pgvector (embeddings)
- **Storage**: AWS S3 (cifrado AES-256)
- **Auth**: JWT + bcrypt (producción: Azure AD / AWS Cognito)
- **AI**: Anthropic Claude API (tagging + RAG)
- **Embeddings**: sentence-transformers / OpenAI embeddings
- **Queue**: Celery + Redis (ingestión async)
- **Deploy**: Docker + Docker Compose → ECS / Kubernetes

## Estructura
```
pathos-backend/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── core/
│   │   ├── config.py            # Settings (env vars)
│   │   ├── security.py          # JWT, hashing, RBAC
│   │   └── dependencies.py      # Shared FastAPI dependencies
│   ├── db/
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   └── init_db.py           # Schema creation + seed
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── document.py
│   │   ├── audit_log.py
│   │   └── embedding.py
│   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── auth.py
│   │   ├── document.py
│   │   └── audit.py
│   ├── services/                # Business logic
│   │   ├── ingest_service.py    # PDF → OCR → tags → embeddings
│   │   ├── rag_service.py       # Vector search + Claude RAG
│   │   ├── storage_service.py   # S3 upload/download
│   │   ├── tagging_service.py   # Claude structured tagging
│   │   └── audit_service.py     # Immutable audit logging
│   └── api/routes/
│       ├── auth.py              # Login, refresh, logout
│       ├── documents.py         # Upload, list, get, delete
│       ├── search.py            # Hybrid search endpoint
│       ├── chat.py              # RAG chat endpoint
│       └── audit.py             # Audit log endpoints
├── scripts/
│   ├── init_db.sql              # PostgreSQL + pgvector schema
│   └── seed_demo.py             # Demo data loader
├── tests/
│   └── test_api.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Módulos principales

### 1. Autenticación (JWT + RBAC)
- Roles: `admin`, `pathologist`, `viewer`
- Tokens: access (30min) + refresh (7d)
- MFA ready (TOTP)
- Producción: integrar con Azure AD / AWS Cognito

### 2. Ingesta de documentos
- Upload seguro a S3 (presigned URL)
- Extracción de texto (PyMuPDF)
- OCR fallback (pytesseract)
- Detección de PHI (regex + NLP)
- Tagging automático con Claude (JSON estructurado)
- Generación de embeddings
- Indexación en pgvector

### 3. RAG
- Búsqueda híbrida: keyword + metadata + vector similarity
- Contexto inyectado al prompt de Claude
- Respuesta con citas exactas (case_id + fecha)
- Streaming support

### 4. Auditoría (HIPAA)
- Log inmutable en tabla append-only
- Campos: user, action, resource, ip, device, timestamp
- Alertas por patrones sospechosos
- Exportación para compliance

## Quick Start

```bash
cp .env.example .env
# Edita .env con tus credenciales

docker-compose up -d
# PostgreSQL + Redis listos

pip install -r requirements.txt
python scripts/init_db.py
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs
