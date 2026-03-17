from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import settings
from app.db.database import init_db
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.chat_and_search import chat_router, search_router
from app.api.routes.audit import router as audit_router

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PathOS starting", env=settings.APP_ENV)
    await init_db()
    yield
    logger.info("PathOS shutting down")

app = FastAPI(title="PathOS — Clinical RAG API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(audit_router, prefix="/api")

@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.APP_ENV}
