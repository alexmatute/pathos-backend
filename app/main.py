"""
PathOS — Clinical RAG System
FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import structlog
import time

from app.core.config import settings
from app.db.database import init_db
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.chat_and_search import chat_router, search_router
from app.api.routes.audit import router as audit_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown logic."""
    logger.info("PathOS starting", env=settings.APP_ENV)
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("PathOS shutting down")


app = FastAPI(
    title="PathOS — Clinical RAG API",
    description="""
## Sistema RAG Clínico para Patólogos

API segura para ingestión, búsqueda y consulta de documentos de patología.

### Módulos
- **Auth**: JWT + RBAC (admin / pathologist / viewer)
- **Documents**: Upload, tagging automático con Claude, descarga segura (S3)
- **Search**: Búsqueda híbrida keyword + metadata + vectorial
- **Chat**: RAG con citas exactas a documentos fuente
- **Audit**: Log inmutable de todos los eventos (HIPAA)

### Seguridad
- Cifrado en tránsito: TLS 1.3
- Cifrado en reposo: AES-256 (S3 SSE)
- Autenticación: JWT + bcrypt (MFA ready)
- Control de acceso: RBAC por rol
- Auditoría: append-only, con alertas de seguridad
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── Middleware ───────────────────────────────────────────────────────────────

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# Trusted hosts (producción)
if settings.APP_ENV == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["pathos.yourdomain.com"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware de logging y timing de todas las requests."""
    start = time.time()
    request_id = request.headers.get("X-Request-ID", "none")

    response = await call_next(request)

    duration = (time.time() - start) * 1000
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration, 2),
        request_id=request_id,
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration:.2f}ms"
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Headers de seguridad en todas las respuestas."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ─── Exception handlers ───────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor. Contacta al administrador."},
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

app.include_router(auth_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(audit_router, prefix="/api")


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "version": "1.0.0",
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "PathOS Clinical RAG API",
        "docs": "/docs",
        "health": "/health",
    }
