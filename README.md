# PathOS — Clinical RAG System

> **Intelligent pathology report management for clinical environments.**
> Built for private medical practice in Sonora, México.

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%20%2B%20pgvector-336791)
![License](https://img.shields.io/badge/license-Proprietary-red)
![Status](https://img.shields.io/badge/status-Active%20Development-brightgreen)

</div>

-----

## What is PathOS?

PathOS is a **secure, internal clinical RAG (Retrieval-Augmented Generation) system** designed for pathologists and clinical staff at a private medical facility in Hermosillo, Sonora. It replaces scattered PDF archives and manual lookup with an AI-powered platform that ingests, indexes, and makes pathology reports instantly queryable in natural language.

### Core capabilities

|Capability           |Description                                                                               |
|---------------------|------------------------------------------------------------------------------------------|
|**Smart ingestion**  |Upload PDFs → automatic OCR, PHI detection, AI tagging, and vector embedding generation   |
|**Hybrid search**    |Natural language queries powered by pgvector (cosine similarity) combined with SQL filters|
|**Clinical RAG chat**|Ask questions in Spanish or English — Claude answers with citations to specific reports   |
|**Telegram alerts**  |Automated critical case notifications via Telegram bot to pathologists and technicians    |
|**HIPAA audit trail**|Immutable logs for every access, upload, and query — full compliance tracking             |

-----
# PathOS — Scope, Mission & Overview

**Version:** 1.0.0  
**Status:** Active Development — 2025  
**Organization:** Private Clinical Laboratory — Hermosillo, Sonora, México  
**Classification:** Confidential — Internal use only

-----

## 1. Executive Summary

PathOS is a secure, AI-powered clinical information system built exclusively for a private pathology laboratory in Hermosillo, Sonora, México. It transforms unstructured pathology reports into a searchable, intelligent knowledge base — enabling clinicians to find case information, identify critical diagnoses, and receive automated alerts in seconds rather than hours.

|Metric                     |Value               |
|---------------------------|--------------------|
|API endpoints              |16                  |
|Vector embedding dimensions|768d                |
|Search response time       |< 100ms             |
|Compliance target          |HIPAA + NOM-024-SSA3|

PathOS addresses three critical gaps in the current clinical workflow:

- Pathology reports are stored as unindexed PDFs with no full-text or semantic search capability
- Clinicians spend significant time manually locating prior cases, biomarker results, or comparative diagnoses
- There is no automated mechanism to escalate critical or malignant findings to the responsible team in real time

-----

## 2. Mission

PathOS exists to reduce the time between a pathology result being produced and a clinician being able to act on it — from hours to seconds.

> **Mission Statement**
> 
> To provide clinicians and pathologists at our facility with immediate, secure, and intelligent access to the complete history of pathology cases — eliminating information silos, accelerating diagnosis workflows, and ensuring no critical finding goes unnoticed.

### 2.1 Core Values

|Value                 |How PathOS embodies it                                                                                                                        |
|----------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
|Patient safety first  |Critical and malignant findings trigger immediate automated alerts to the responsible pathologist via Telegram — no manual monitoring required|
|Privacy by design     |All patient data is classified as PHI. Detection is automatic. Access requires authentication. Every action is logged permanently             |
|Clinical accuracy     |Claude-powered RAG answers are grounded in the actual indexed report content and always cite the source case ID and date                      |
|Operational efficiency|What took minutes of manual PDF search now resolves in under 100ms via pgvector cosine similarity                                             |
|Regulatory compliance |Immutable audit logs aligned with HIPAA standards and NOM-024-SSA3 (Mexican electronic clinical records regulation)                           |

### 2.2 What PathOS is not

- **Not a diagnostic tool** — PathOS does not generate medical diagnoses. It retrieves and presents existing clinical findings
- **Not a replacement for the pathologist** — all clinical judgments remain with the licensed professional
- **Not a public-facing product** — it is an internal system for authorized facility staff only
- **Not a generic document management system** — it is purpose-built for pathology workflows

-----

## 3. Project Overview

### 3.1 System description

PathOS combines a FastAPI backend, a PostgreSQL 15 database with the pgvector extension, a React frontend, and the Anthropic Claude API to create a closed-loop clinical intelligence platform. Documents enter through a five-stage automated pipeline and exit as queryable, cited knowledge available through a web interface and a Telegram bot.

### 3.2 Ingestion pipeline

|Stage            |Technology                               |Output                                                     |
|-----------------|-----------------------------------------|-----------------------------------------------------------|
|1 — Upload       |multipart/form-data → FastAPI            |Raw file stored, background job queued                     |
|2 — OCR          |Tesseract + PyMuPDF                      |Full extracted text                                        |
|3 — PHI detection|Regex (SSN, MRN, DOB, phone, NPI)        |PHI flags, sensitivity classification                      |
|4 — AI tagging   |Anthropic Claude — JSON structured output|organ_system, malignancy, priority, diagnosis_summary, tags|
|5 — Embedding    |sentence-transformers (all-mpnet, 768d)  |Vector stored in pgvector HNSW index                       |

All five stages execute asynchronously via the Celery worker. The API returns a document ID immediately on upload.

### 3.3 Query capabilities

|Mode         |Description                                                                                                                                |Endpoint          |
|-------------|-------------------------------------------------------------------------------------------------------------------------------------------|------------------|
|Hybrid search|Combines cosine vector similarity (pgvector HNSW) with SQL filters for organ, malignancy, priority, and status                             |`POST /api/search`|
|RAG chat     |Natural language questions answered by Claude using retrieved document chunks as context. Answers always cite the source `case_id` and date|`POST /api/chat`  |
|Telegram bot |Subset of search and chat accessible via the facility’s Telegram bot — optimized for mobile and on-call workflows                          |`@pathos_bot`     |

### 3.4 Access control

PathOS enforces role-based access control (RBAC) with three roles. All authentication is JWT-based with 30-minute access tokens and 7-day refresh tokens.

|Role         |Permissions                                                                      |Typical user                           |
|-------------|---------------------------------------------------------------------------------|---------------------------------------|
|`admin`      |Full system access — create users, view all audit logs, manage all documents     |System administrator                   |
|`pathologist`|Upload, search, RAG chat, receive Telegram alerts, view all documents            |Senior pathologist, attending physician|
|`viewer`     |Read-only access to documents and search results. Cannot upload or trigger alerts|Resident, extern, read-only staff      |

-----

## 4. Project Scope

### 4.1 In scope

#### Document management

- Upload of PDF, DOCX, and TXT pathology reports up to 50 MB per file
- Automatic OCR text extraction using Tesseract and PyMuPDF
- Automatic PHI detection (SSN, MRN, date of birth, phone number, email, NPI formats)
- AI-powered metadata tagging via Anthropic Claude: document type, organ system, malignancy classification, priority, diagnosis summary
- Vector embedding generation (768 dimensions) stored in PostgreSQL with pgvector HNSW index
- Document download via pre-signed URL
- Manual tag editing by pathologists and administrators
- Soft delete with audit trail preservation

#### Search and retrieval

- Hybrid semantic + keyword search with cosine similarity scoring
- Filter by organ system, malignancy, priority, status, and date range
- Search result ranking by vector similarity score
- Full document detail view including all AI-generated metadata

#### AI-assisted clinical chat

- Natural language question answering against the indexed document repository
- Conversation history support (multi-turn queries)
- Mandatory source citations in every response (`case_id` + date)
- Fallback handling when no relevant documents are found

#### Notifications and alerts

- Telegram bot with commands: `/start`, `/resumen`, `/alertas`, `/notificar`, free-text RAG query, PDF upload
- Automated daily morning report (7:00 AM, weekdays)
- Automated midday critical case review (1:00 PM, weekdays)
- Automated every-30-minute critical case monitor (8 AM–6 PM, weekdays)
- Webhook-triggered real-time alerts for newly ingested critical or malignant documents

#### Security and compliance

- JWT authentication with role-based access control (admin / pathologist / viewer)
- bcrypt password hashing (cost factor 12)
- Immutable append-only audit log for all user actions
- CORS configuration restricting access to authorized frontend domains only
- PHI classification and tagging on all patient-related documents

#### Infrastructure

- Docker Compose with four services: FastAPI API, Celery worker, PostgreSQL 15 + pgvector, Redis
- Nginx reverse proxy serving frontend (`tudominio.com`) and API (`api.tudominio.com`) from a single GCP VM
- SSL/TLS via Let’s Encrypt with automatic certificate renewal
- Deployment target: Google Cloud Platform — e2-standard-2 (2 vCPU, 8 GB RAM, 50 GB SSD)
- File storage: Google Cloud Storage (production) / local filesystem (development)

-----

### 4.2 Out of scope

> ⚠️ The following capabilities are **not** included in PathOS v1.0 and are not planned unless explicitly approved by the facility owners.

- AI-generated diagnoses or clinical recommendations
- Integration with external EMR/EHR systems (Epic, SAP Health, or similar)
- Patient-facing portal or any form of public access
- Billing or insurance claim processing
- Image analysis of histopathology slides (scanned microscopy images)
- Multi-facility or multi-tenant deployment
- Real-time collaboration or multi-user document editing
- Native mobile application (iOS / Android)

-----

### 4.3 Technical constraints

|Constraint          |Detail                                                                   |
|--------------------|-------------------------------------------------------------------------|
|Maximum file size   |50 MB per document upload                                                |
|Supported file types|PDF (primary), DOCX, TXT                                                 |
|Embedding model     |sentence-transformers/all-mpnet-base-v2 — 768 dimensions, English/Spanish|
|LLM provider        |Anthropic Claude only — no local model fallback in v1.0                  |
|Cloud provider      |Google Cloud Platform — VM-based, not serverless                         |
|Deployment model    |Single VM, single region — no multi-zone redundancy in v1.0              |
|Authentication      |JWT only — no OAuth2, SAML, or SSO in v1.0                               |
|Language support    |Spanish (primary UI and reports) and English (API, code, documentation)  |

-----

## 5. Stakeholders

|Role                        |Responsibilities in PathOS                                                                                                                           |
|----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
|Pathologist *(primary user)*|Performs searches and RAG queries. Reviews AI-generated tags for accuracy. Receives and acts on Telegram alerts. Uploads case documents.             |
|Laboratory technician       |Uploads pathology PDFs into the system. Monitors ingestion status. Sends notifications to the technicians group via `/notificar`.                    |
|Facility administrator      |Manages user accounts and role assignments. Reviews the full audit trail. Monitors system health and security alerts.                                |
|System developer            |Maintains the codebase, deploys updates, manages GCP infrastructure, and integrates new AI capabilities as they become available.                    |
|External AI provider        |Anthropic — provides the Claude API for auto-tagging and RAG responses. Subject to API rate limits and usage costs.                                  |
|Regulatory framework        |HIPAA (data handling) and NOM-024-SSA3 (Mexican electronic clinical records). PathOS is designed to support compliance, not to replace legal counsel.|

-----

## 6. Assumptions and Risks

### 6.1 Key assumptions

- All users access PathOS through the facility’s internal network or a trusted, authenticated device
- Pathology reports uploaded to the system are final or near-final — drafts may receive inaccurate AI-generated tags
- The Anthropic API remains available and costs remain within budget; the system degrades gracefully if unavailable (tagging falls back to defaults, chat is disabled)
- The GCP VM remains running; a restart restores all services automatically via Docker’s `restart: unless-stopped` policy
- Users understand that PathOS is a support tool — clinical decisions remain the responsibility of the licensed pathologist

### 6.2 Risk register

|Risk                            |Likelihood|Mitigation                                                                                                           |
|--------------------------------|----------|---------------------------------------------------------------------------------------------------------------------|
|PHI leak via uncontrolled export|Low       |All downloads require authentication. PHI detection flags sensitive documents. Audit log records every access event. |
|AI tagging inaccuracy           |Medium    |Tags are AI-generated suggestions, not authoritative. Pathologists review and can edit any tag at any time.          |
|Anthropic API downtime          |Low       |Ingestion pipeline falls back to default tags. RAG chat is disabled with a clear user-facing message.                |
|Unauthorized access attempt     |Low       |JWT authentication, bcrypt hashing, and audit logs with login failure tracking. Alerts for repeated failures.        |
|GCP VM failure                  |Low       |Docker restart policy restores services on reboot. Patient data persists in the PostgreSQL volume.                   |
|Storage cost growth             |Medium    |Documents are stored in GCS Standard tier. Cost scales linearly with volume — monitor monthly via GCP billing alerts.|

-----

## 7. Regulatory and Compliance Alignment

PathOS is designed to support — but not replace — formal compliance programs. The table below maps system controls to applicable standards.

|Requirement                      |Standard                  |PathOS control                                                                            |
|---------------------------------|--------------------------|------------------------------------------------------------------------------------------|
|Access control                   |HIPAA § 164.312(a)(1)     |JWT authentication, RBAC with three roles, session expiration                             |
|Audit controls                   |HIPAA § 164.312(b)        |Append-only audit log recording all access, queries, uploads, and login events            |
|Automatic logoff                 |HIPAA § 164.312(a)(2)(iii)|30-minute JWT token expiration with refresh flow                                          |
|PHI safeguards                   |HIPAA § 164.312(e)(2)(ii) |PHI auto-detection and tagging; all data transmitted via HTTPS only                       |
|Electronic clinical record format|NOM-024-SSA3 (México)     |Document metadata, creator ID, timestamps, and audit trail preserved for all records      |
|Data integrity                   |HIPAA § 164.312(c)(1)     |PostgreSQL ACID transactions; immutable audit log; pgvector embeddings tied to document ID|


> **Note:** Consult qualified legal counsel before using this compliance mapping for formal certification or regulatory submissions.

-----

## 8. Delivery and Deployment

### 8.1 Deployment environment

|Component             |Specification                                                |
|----------------------|-------------------------------------------------------------|
|Cloud provider        |Google Cloud Platform                                        |
|VM type               |e2-standard-2 — 2 vCPU, 8 GB RAM, 50 GB SSD                  |
|Operating system      |Ubuntu 22.04 LTS                                             |
|Containerization      |Docker Compose — four services (api, worker, postgres, redis)|
|Frontend hosting      |Nginx serving React build at `tudominio.com`                 |
|API hosting           |Nginx reverse proxy at `api.tudominio.com` → `localhost:8000`|
|SSL/TLS               |Let’s Encrypt — auto-renewing via certbot                    |
|File storage          |Google Cloud Storage — Standard tier                         |
|Estimated monthly cost|~$55 USD/month (covered by $300 GCP free trial for ~5 months)|

### 8.2 Repositories

|Repository                            |Contents                                                                              |
|--------------------------------------|--------------------------------------------------------------------------------------|
|`github.com/alexmatute/pathos-backend`|FastAPI application, Celery worker, Docker Compose, database models, services, schemas|
|`github.com/alexmatute/pathos-ui`     |React 18 + Vite frontend, production environment configuration                        |

### 8.3 Update process

All code changes are pushed to GitHub and deployed to the GCP VM using the `~/deploy.sh` script, which pulls the latest code, rebuilds Docker images, and recompiles the React frontend without downtime.

-----

## 9. Glossary

|Term            |Definition                                                                                                                                              |
|----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
|**RAG**         |Retrieval-Augmented Generation — an AI technique that retrieves relevant documents from a knowledge base and uses them as context for generating answers|
|**pgvector**    |A PostgreSQL extension that adds vector data types and similarity search operators, enabling semantic search directly in the database                   |
|**HNSW**        |Hierarchical Navigable Small World — a graph-based approximate nearest neighbor algorithm used for fast vector similarity search                        |
|**Embedding**   |A numerical vector representation of text, capturing semantic meaning so that similar texts produce similar vectors                                     |
|**PHI**         |Protected Health Information — any data that can identify a patient (name, MRN, SSN, date of birth, etc.)                                               |
|**JWT**         |JSON Web Token — a signed, self-contained token used for stateless authentication between client and server                                             |
|**RBAC**        |Role-Based Access Control — a method of regulating access by assigning permissions to roles rather than to individual users                             |
|**Celery**      |A distributed task queue for Python used to execute background jobs asynchronously (OCR, embedding generation, notifications)                           |
|**n8n**         |A workflow automation platform used to orchestrate the Telegram bot, scheduled alerts, and email notifications                                          |
|**NOM-024-SSA3**|Mexican Official Standard governing the interoperability and security requirements for health information systems and electronic clinical records       |

-----

## Repository structure

```
pathos-backend/               # FastAPI backend — this repository
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── auth.py               # JWT authentication + user management
│   │       ├── documents.py          # Document upload, list, download, tags
│   │       ├── chat_and_search.py    # RAG chat + vector search
│   │       └── audit.py             # Audit logs + summary
│   ├── core/
│   │   ├── config.py                # Pydantic settings (env vars)
│   │   └── security.py             # JWT, bcrypt, RBAC, get_current_user
│   ├── db/
│   │   └── database.py             # SQLAlchemy async engine + session
│   ├── models/
│   │   ├── document.py             # Document ORM model
│   │   ├── user.py                 # User ORM model
│   │   ├── audit_log.py            # Immutable audit log model
│   │   └── embedding.py            # pgvector embedding model
│   ├── schemas/
│   │   └── schemas.py              # Pydantic request/response schemas
│   ├── services/
│   │   ├── ingest_service.py       # OCR → PHI → Claude tagging pipeline
│   │   ├── rag_service.py          # Vector search + Claude RAG
│   │   ├── storage_service.py      # GCS / S3 / local storage adapter
│   │   └── audit_service.py        # Audit event logging
│   ├── main.py                     # FastAPI app + CORS + routers
│   └── worker.py                   # Celery worker tasks
├── scripts/
│   └── init_db.sql                 # Database schema + pgvector extension
├── docs/
│   ├── PathOS_GCP_Backend_Deploy.md    # Full GCP deployment guide
│   └── PathOS_System_Overview.html    # Architecture + UML diagrams
├── docker-compose.yml              # Full local stack
├── Dockerfile
├── requirements.txt
├── .env.example
└── .gitignore

pathos-ui/                    # React frontend — separate repository
├── src/
│   └── App.jsx               # Single-file React app (Vite)
├── .env.production           # VITE_API_URL for production
└── package.json
```

-----

## Tech stack

### Backend

|Layer           |Technology                                     |
|----------------|-----------------------------------------------|
|API framework   |FastAPI 0.111 + Uvicorn                        |
|Language        |Python 3.11                                    |
|ORM             |SQLAlchemy 2.0 (async)                         |
|Validation      |Pydantic v2                                    |
|Auth            |JWT (python-jose) + bcrypt                     |
|Task queue      |Celery 5.4 + Redis 7                           |
|OCR             |PyMuPDF + Tesseract                            |
|AI tagging + RAG|Anthropic Claude (claude-sonnet-4)             |
|Embeddings      |sentence-transformers (all-mpnet-base-v2, 768d)|

### Data

|Component       |Technology                                        |
|----------------|--------------------------------------------------|
|Primary database|PostgreSQL 15                                     |
|Vector search   |pgvector 0.2.5 with HNSW index (cosine similarity)|
|Cache / broker  |Redis 7                                           |
|File storage    |Local (dev) / Google Cloud Storage (prod)         |

### Frontend & Infrastructure

|Component       |Technology                              |
|----------------|----------------------------------------|
|Frontend        |React 18 + Vite                         |
|Reverse proxy   |Nginx + Let’s Encrypt (SSL)             |
|Containerization|Docker Compose                          |
|Deployment      |Google Cloud Platform — e2-standard-2 VM|
|Automation      |n8n Cloud                               |
|Notifications   |Telegram Bot API                        |

-----

## System architecture

```
                          HTTPS (:443)
                              │
              ┌───────────────┴───────────────┐
              │         Nginx (VM GCP)         │
              │  tudominio.com  →  /var/www    │
              │  api.tudominio.com → :8000     │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │    FastAPI Backend (:8000)     │
              │  JWT + RBAC · 16 endpoints     │
              └──┬──────────┬──────────┬──────┘
                 │          │          │
         ┌───────▼──┐  ┌────▼────┐  ┌─▼──────────┐
         │PostgreSQL│  │  Redis  │  │ Claude API  │
         │+pgvector │  │ (queue) │  │ (Anthropic) │
         └──────────┘  └────┬────┘  └────────────┘
                            │
                     ┌──────▼──────┐
                     │Celery Worker│
                     │OCR·PHI·Embed│
                     └──────┬──────┘
                            │ webhook
                     ┌──────▼──────┐     ┌──────────────┐
                     │  n8n Cloud  │────►│ Telegram Bot │
                     └─────────────┘     └──────────────┘
```

-----

## Data model

```
Document
├── id                UUID (PK)
├── case_id           string
├── patient_id        string
├── filename          string
├── document_type     enum: pathology_report | biopsy | cytology | immunohistochemistry | lab_result
├── organ_system      string?
├── malignancy        enum: malignant | suspicious | benign | undetermined
├── priority          enum: critical | urgent | routine
├── status            enum: draft | final | amended
├── diagnosis_summary string?
├── contains_phi      bool
├── tags              list[string]
├── s3_key            string
└── created_at        datetime

DocumentEmbedding
├── id                UUID (PK)
├── document_id       UUID (FK → Document)
├── chunk_index       int
├── chunk_text        string
├── embedding         vector(768)          ← pgvector
└── model             string

User
├── id                UUID (PK)
├── email             string (unique)
├── full_name         string
├── hashed_password   string
├── role              enum: admin | pathologist | viewer
├── facility          string?
└── is_active         bool

AuditLog
├── id                UUID (PK)
├── user_id           UUID (FK → User)
├── action            enum: LOGIN | LOGOUT | DOCUMENT_VIEW | DOCUMENT_INGEST | RAG_QUERY | USER_CREATED | LOGIN_FAILED
├── resource_id       string?
├── ip_address        string?
├── status            string
└── created_at        datetime
```

-----

## API reference

**Base URL:** `https://api.tudominio.com`

All endpoints except `/health` and `POST /api/auth/login` require:

```
Authorization: Bearer <access_token>
```

### Authentication

|Method|Endpoint           |Description                                |
|------|-------------------|-------------------------------------------|
|`POST`|`/api/auth/login`  |Login — returns JWT access + refresh tokens|
|`GET` |`/api/auth/me`     |Current authenticated user profile         |
|`POST`|`/api/auth/refresh`|Refresh access token                       |
|`POST`|`/api/auth/users`  |Create user *(admin only)*                 |
|`POST`|`/api/auth/logout` |Invalidate session                         |

### Documents

|Method  |Endpoint                          |Description                                  |
|--------|----------------------------------|---------------------------------------------|
|`POST`  |`/api/documents/upload`           |Upload PDF — triggers full ingestion pipeline|
|`GET`   |`/api/documents`                  |List documents with optional filters         |
|`GET`   |`/api/documents/{id}`             |Get single document                          |
|`GET`   |`/api/documents/{id}/download-url`|Generate pre-signed download URL             |
|`PATCH` |`/api/documents/{id}/tags`        |Update document tags                         |
|`DELETE`|`/api/documents/{id}`             |Delete document                              |

### Search & Chat

|Method|Endpoint     |Description                       |
|------|-------------|----------------------------------|
|`POST`|`/api/search`|Hybrid vector + SQL search        |
|`POST`|`/api/chat`  |RAG chat with conversation history|

### Audit

|Method|Endpoint            |Description                |
|------|--------------------|---------------------------|
|`GET` |`/api/audit`        |List audit logs            |
|`GET` |`/api/audit/summary`|Aggregate access statistics|

### Health

|Method|Endpoint |Description        |
|------|---------|-------------------|
|`GET` |`/health`|System health check|

-----

## Getting started (local development)

### Prerequisites

- Docker Desktop 24+ with Docker Compose v2
- Git
- An [Anthropic API key](https://console.anthropic.com)
- Python 3.11 (only for generating the bcrypt hash during setup)

### 1. Clone the repository

```bash
git clone https://github.com/alexmatute/pathos-backend.git
cd pathos-backend
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in the required values:

```bash
# Required — generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-random-64-char-string

# Required — get from console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-api03-...

# Pre-configured for local Docker — do not change these
DATABASE_URL=postgresql+asyncpg://pathos:pathos_pass@postgres:5432/pathos_db
REDIS_URL=redis://:redis_pass@redis:6379/0
STORAGE_BACKEND=local
APP_ENV=development
```

### 3. Start the stack

```bash
docker compose up --build -d
```

The first run takes 3–5 minutes to pull images and install Python dependencies.

### 4. Verify the API is running

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","env":"development"}
```

Open **http://localhost:8000/docs** for the full interactive Swagger UI.

### 5. Create the admin user

```bash
HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'Admin1234!', bcrypt.gensalt(12)).decode())")

docker exec -it pathos_postgres psql -U pathos -d pathos_db -c "
INSERT INTO users (id, email, full_name, hashed_password, role, facility, is_active, created_at)
VALUES (gen_random_uuid(), 'admin@pathos.med', 'Administrator', '$HASH', 'admin', 'PathOS', true, NOW())
ON CONFLICT (email) DO NOTHING;
"
```

### 6. Test login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@pathos.med","password":"Admin1234!"}'
# Expected: {"access_token":"eyJ...","token_type":"bearer",...}
```

### 7. Run the frontend

```bash
git clone https://github.com/alexmatute/pathos-ui.git
cd pathos-ui && npm install && npm run dev
# Open http://localhost:5173
```

-----

## Useful Docker commands

```bash
# Service status
docker compose ps

# Stream logs
docker compose logs -f api
docker compose logs -f worker

# Restart API after code changes
docker compose restart api

# PostgreSQL shell
docker exec -it pathos_postgres psql -U pathos -d pathos_db

# API container shell
docker exec -it pathos_api bash

# Stop all services
docker compose down

# Stop and wipe all data  ⚠️
docker compose down -v

# Free up disk space
docker system prune -a
```

-----

## Environment variables reference

|Variable                       |Required |Default|Description                         |
|-------------------------------|---------|-------|------------------------------------|
|`APP_ENV`                      |✅        |—      |`development` or `production`       |
|`SECRET_KEY`                   |✅        |—      |JWT signing key (64+ random chars)  |
|`ANTHROPIC_API_KEY`            |✅        |—      |Claude API key                      |
|`DATABASE_URL`                 |✅        |—      |Async PostgreSQL connection string  |
|`REDIS_URL`                    |✅        |—      |Redis connection string             |
|`STORAGE_BACKEND`              |✅        |`local`|`local` | `gcs` | `s3`              |
|`ALLOWED_ORIGINS`              |prod only|—      |Comma-separated CORS origins        |
|`GCS_BUCKET_NAME`              |if GCS   |—      |Google Cloud Storage bucket         |
|`GCS_PROJECT_ID`               |if GCS   |—      |GCP project ID                      |
|`N8N_WEBHOOK_URL`              |optional |—      |n8n webhook for critical case alerts|
|`TELEGRAM_BOT_TOKEN`           |optional |—      |Telegram bot token from @BotFather  |
|`TELEGRAM_ALLOWED_USERS`       |optional |—      |Comma-separated allowed Telegram IDs|
|`TELEGRAM_TECHNICIANS_GROUP_ID`|optional |—      |Telegram group ID (negative number) |
|`ACCESS_TOKEN_EXPIRE_MINUTES`  |—        |`30`   |JWT access token lifetime           |
|`REFRESH_TOKEN_EXPIRE_DAYS`    |—        |`7`    |JWT refresh token lifetime          |
|`EMBEDDING_DIM`                |—        |`768`  |Vector embedding dimensions         |
|`MAX_FILE_SIZE_MB`             |—        |`50`   |Maximum upload file size            |

-----

## Access control

PathOS uses role-based access control (RBAC) with three roles:

|Role         |Permissions                                                                        |
|-------------|-----------------------------------------------------------------------------------|
|`admin`      |Full system access — create/manage users, view all audit logs, access all documents|
|`pathologist`|Upload documents, search, use RAG chat, receive Telegram alerts                    |
|`viewer`     |Read-only access to documents and search results                                   |

-----

## Security

- Passwords are hashed with **bcrypt** (cost factor 12)
- JWT access tokens expire after **30 minutes**; refresh tokens after **7 days**
- All patient data is treated as PHI — detected via regex (SSN, MRN, DOB, phone, email, NPI formats)
- The `.env` file is in `.gitignore` and must **never** be committed to any repository
- Audit logs are **append-only** — they cannot be modified or deleted through the API
- In production, PostgreSQL and Redis ports must **not** be exposed to the internet

-----

## Production deployment

The complete step-by-step guide is in [`docs/PathOS_GCP_Backend_Deploy.md`](docs/PathOS_GCP_Backend_Deploy.md).

**Summary — Google Cloud Platform:**

1. Create VM (e2-standard-2, Ubuntu 22.04, 50GB SSD)
1. Reserve a static IP and configure DNS (`tudominio.com`, `api.tudominio.com`)
1. SSH into the VM → install Docker, Node.js 20, Nginx
1. Clone `pathos-backend` and `pathos-ui`
1. Configure `.env` with production values
1. `docker compose up --build -d`
1. Build React frontend (`npm run build`) → copy to `/var/www/pathos`
1. Configure Nginx reverse proxy for both domains
1. `certbot --nginx` for free SSL via Let’s Encrypt

**Estimated monthly cost:** ~$55 USD on GCP.
With the $300 free credit → **approximately 5 months free**.

-----

## n8n + Telegram integration

Full setup guide in [`docs/PathOS_Lovable_n8n_Guide.md`](docs/PathOS_Lovable_n8n_Guide.md).

**Telegram bot commands:**

|Command               |Description                                               |
|----------------------|----------------------------------------------------------|
|`/start`              |Welcome message and available commands                    |
|`/resumen`            |Repository statistics (total docs, queries, alerts)       |
|`/alertas`            |List active critical and urgent cases                     |
|`/notificar [message]`|Forward message to the technicians group                  |
|`[free text]`         |Natural language RAG query against the document repository|
|`[PDF attachment]`    |Ingest document directly through the chat                 |

The n8n instance runs three scheduled workflows:

- **Morning report** — daily summary at 7:00 AM (weekdays)
- **Midday review** — critical case check at 1:00 PM (weekdays)
- **Continuous monitor** — checks for new critical cases every 30 minutes, 8 AM–6 PM

-----

## Ingestion pipeline

When a PDF is uploaded, the following steps execute automatically via the Celery worker:

```
Upload → OCR (Tesseract + PyMuPDF) → PHI detection (regex)
      → Claude auto-tagging (JSON metadata) → Embedding (768d)
      → pgvector HNSW index → ✅ Ready for RAG queries
```

The entire pipeline runs asynchronously — the API returns immediately with a document ID, and the worker processes the file in the background.

-----

## Project context

PathOS is an **internal proprietary system** developed exclusively for a private clinical laboratory in Hermosillo, Sonora, México. It is not an open-source project.

|                             |                                                           |
|-----------------------------|-----------------------------------------------------------|
|**Industry**                 |Clinical pathology / healthcare                            |
|**Location**                 |Hermosillo, Sonora, México                                 |
|**Primary compliance target**|HIPAA (data handling standards)                            |
|**Secondary compliance**     |NOM-024-SSA3 (electronic clinical records, México)         |
|**Language support**         |Spanish (primary — UI, reports) · English (API, code, docs)|
|**Data classification**      |All patient records classified as PHI                      |

-----

## Contributing

This is a closed internal project. All changes go through `main` on GitHub.

### Deploy workflow

```bash
# 1. Develop and test locally
docker compose up -d
# verify at localhost:8000 and localhost:5173

# 2. Commit
git add .
git commit -m "type: brief description"
git push origin main

# 3. Deploy on the production server
ssh user@pathos-server
~/deploy.sh
```

### Commit format

```
feat:     new feature or capability
fix:      bug fix
docs:     documentation changes only
refactor: code restructuring without behavior change
chore:    dependency updates, config, CI
security: security-related changes
```

-----

## License

**Proprietary — All rights reserved.**

This software and its source code are the exclusive property of the operating company. Unauthorized copying, distribution, modification, or use of this code — in whole or in part — is strictly prohibited without prior written authorization from the owners.

Violations may be subject to legal action under applicable Mexican and international intellectual property law.

© 2025 — Private clinical laboratory, Hermosillo, Sonora, México.

-----

<div align="center">

Built with **FastAPI** · **PostgreSQL + pgvector** · **Claude (Anthropic)** · **Docker** · **n8n** · **Telegram**

*PathOS v1.0 — Hermosillo, Sonora, México*

</div>
