import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.documents import router as documents_router
from app.api.v1.events import router as events_router
from app.api.v1.chat import router as chat_router
from app.api.v1.vision import router as vision_router
from app.core.config import settings
from app.core.logging import logger
from app.services.providers.factory import ProviderFactory


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure directories and log environment
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)

    ollama_ok = await ProviderFactory.is_ollama_available()
    logger.info(
        "Application starting up",
        extra={
            "environment": settings.ENVIRONMENT,
            "ollama_available": ollama_ok,
            "storage_path": str(settings.storage_path),
            "fallback_embeddings": settings.FALLBACK_EMBEDDINGS,
        },
    )
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="AI-OCR-Sprint Multimodal RAG API",
    description="Productive interactive multimodal RAG system for complex PDF documents.",
    version="1.0.0",
    lifespan=lifespan,
)

from app.core.security import SecurityException

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SecurityException)
async def security_exception_handler(request: Request, exc: SecurityException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
        headers=dict(exc.headers or {}),
    )


# Request Latency & Observability Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time

    # Omit SSE streaming endpoints from verbose single-line logs
    if not request.url.path.endswith("/events"):
        logger.info(
            "HTTP request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_s": round(duration, 4),
            },
        )
    return response


# Register v1 Routers
app.include_router(documents_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(vision_router, prefix="/api/v1")


@app.get("/health", summary="Health check endpoint")
async def health_check():
    ollama_ok = await ProviderFactory.is_ollama_available()
    return {
        "status": "healthy",
        "service": "AI-OCR-Sprint API",
        "ollama_connected": ollama_ok,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", summary="Root API Info")
async def root():
    return {
        "message": "AI-OCR-Sprint Multimodal RAG Engine",
        "docs_url": "/docs",
        "version": "1.0.0",
    }
