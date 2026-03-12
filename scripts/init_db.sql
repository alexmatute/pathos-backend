-- ============================================================
-- PathOS — PostgreSQL Schema
-- Requiere: PostgreSQL 15+ con extensión pgvector
-- ============================================================

-- Extensión vectorial
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Tipos ENUM ──────────────────────────────────────────────────────────────

CREATE TYPE user_role AS ENUM ('admin', 'pathologist', 'viewer');
CREATE TYPE doc_type AS ENUM (
    'pathology_report', 'biopsy', 'cytology',
    'immunohistochemistry', 'lab_result', 'consent', 'image_note'
);
CREATE TYPE doc_status AS ENUM ('draft', 'final', 'amended');
CREATE TYPE doc_sensitivity AS ENUM ('PHI', 'de-identified', 'restricted');
CREATE TYPE organ_system AS ENUM (
    'breast', 'colon', 'prostate', 'skin', 'lung',
    'liver', 'kidney', 'thyroid', 'brain', 'bladder', 'other'
);
CREATE TYPE malignancy AS ENUM ('benign', 'suspicious', 'malignant', 'undetermined');
CREATE TYPE priority AS ENUM ('routine', 'urgent', 'critical');
CREATE TYPE audit_action AS ENUM (
    'LOGIN', 'LOGIN_FAILED', 'LOGOUT',
    'DOCUMENT_VIEW', 'DOCUMENT_UPLOAD', 'DOCUMENT_DELETE',
    'DOCUMENT_DOWNLOAD', 'DOCUMENT_INGEST', 'DOCUMENT_TAGGED',
    'RAG_QUERY', 'RAG_RESPONSE', 'SEARCH_QUERY',
    'USER_CREATED', 'USER_UPDATED', 'USER_DEACTIVATED', 'EXPORT'
);
CREATE TYPE audit_status AS ENUM ('success', 'failure', 'alert');

-- ─── Tabla: users ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role            user_role NOT NULL DEFAULT 'pathologist',
    facility        VARCHAR(255),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    mfa_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret      VARCHAR(64),
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- ─── Tabla: documents ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS documents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id             VARCHAR(100) UNIQUE NOT NULL,
    patient_id          VARCHAR(100) NOT NULL,
    specimen_id         VARCHAR(100),
    filename            VARCHAR(512) NOT NULL,
    s3_key              VARCHAR(1024) NOT NULL,
    s3_bucket           VARCHAR(255) NOT NULL,
    file_size_bytes     INTEGER,
    page_count          INTEGER,
    checksum_sha256     VARCHAR(64),
    mime_type           VARCHAR(128) DEFAULT 'application/pdf',

    -- Tags clínicos
    document_type       doc_type NOT NULL DEFAULT 'pathology_report',
    status              doc_status NOT NULL DEFAULT 'draft',
    sensitivity         doc_sensitivity NOT NULL DEFAULT 'PHI',
    retention_class     VARCHAR(64) DEFAULT '7-years-clinical',
    organ_system        organ_system,
    malignancy          malignancy,
    priority            priority DEFAULT 'routine',
    stain_type          VARCHAR(128),
    biomarker           VARCHAR(255),
    diagnosis_code      VARCHAR(32),
    diagnosis_summary   TEXT,
    followup_required   BOOLEAN DEFAULT FALSE,

    -- Fechas
    study_date          DATE,
    received_date       DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Procesamiento
    ocr_applied         BOOLEAN DEFAULT FALSE,
    ocr_confidence      FLOAT,
    contains_phi        BOOLEAN DEFAULT TRUE,
    phi_entities        JSONB,
    raw_text            TEXT,
    language            VARCHAR(10) DEFAULT 'es',
    tags                JSONB DEFAULT '[]',

    -- Autor
    author_id           UUID REFERENCES users(id) ON DELETE SET NULL,
    facility            VARCHAR(255)
);

CREATE INDEX idx_documents_patient_id ON documents(patient_id);
CREATE INDEX idx_documents_case_id ON documents(case_id);
CREATE INDEX idx_documents_document_type ON documents(document_type);
CREATE INDEX idx_documents_organ_system ON documents(organ_system);
CREATE INDEX idx_documents_malignancy ON documents(malignancy);
CREATE INDEX idx_documents_priority ON documents(priority);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_study_date ON documents(study_date);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);

-- Full-text search en español
CREATE INDEX idx_documents_fts ON documents USING gin(
    to_tsvector('spanish', coalesce(diagnosis_summary, '') || ' ' || coalesce(filename, ''))
);

-- ─── Tabla: document_embeddings ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS document_embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID UNIQUE NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    embedding       vector(768),                -- all-mpnet-base-v2
    embedded_text   TEXT,
    embedding_model VARCHAR(255),
    chunk_index     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índice HNSW para búsqueda vectorial rápida (similitud coseno)
CREATE INDEX idx_embeddings_hnsw ON document_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ─── Tabla: audit_logs (append-only, HIPAA) ───────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    user_email      VARCHAR(255),
    user_role       VARCHAR(32),
    action          audit_action NOT NULL,
    resource_type   VARCHAR(64),
    resource_id     VARCHAR(255),
    resource_name   VARCHAR(512),
    detail          TEXT,
    ip_address      VARCHAR(64),
    user_agent      VARCHAR(512),
    device_hint     VARCHAR(128),
    session_id      VARCHAR(128),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          audit_status NOT NULL DEFAULT 'success'
);

CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_status ON audit_logs(status);
CREATE INDEX idx_audit_ip ON audit_logs(ip_address);

-- Política de inmutabilidad: deshabilitar UPDATE y DELETE en audit_logs
-- (activar en producción con Row Level Security)
-- ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY audit_append_only ON audit_logs FOR UPDATE USING (FALSE);
-- CREATE POLICY audit_no_delete ON audit_logs FOR DELETE USING (FALSE);


-- ─── Trigger: updated_at automático ──────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ─── Usuario admin por defecto ────────────────────────────────────────────────
-- Contraseña: Admin1234! (cambiar INMEDIATAMENTE en producción)
-- Hash bcrypt generado con: passlib.hash.bcrypt.hash("Admin1234!")

INSERT INTO users (email, full_name, hashed_password, role, facility)
VALUES (
    'admin@pathos.local',
    'Administrador PathOS',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'admin',
    'Hospital Universitario'
) ON CONFLICT (email) DO NOTHING;
