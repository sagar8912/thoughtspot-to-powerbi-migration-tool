"""
FastAPI application for ThoughtSpot -> Power BI Migration Tool.
"""

import sys
import logging
from contextlib import asynccontextmanager
from api.routers import jobs, websocket, migration
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from api.config import config
from storage.database import init_database


# ============================================================
# Logging Configuration
# ============================================================

LOG_LEVEL = getattr(config, "LOG_LEVEL", "INFO")

logger.remove()
logger.add(
    sys.stderr,
    level=LOG_LEVEL,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    colorize=True,
)


class InterceptHandler(logging.Handler):
    """
    Intercept standard Python logging and route it through loguru.
    """

    def emit(self, record: logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2

        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


logging.basicConfig(
    handlers=[InterceptHandler()],
    level=LOG_LEVEL,
    force=True,
)

for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
    logging.getLogger(logger_name).handlers = [InterceptHandler()]
    logging.getLogger(logger_name).propagate = False


# ============================================================
# Lifespan Events
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events for FastAPI application.
    """

    logger.info("Starting ThoughtSpot -> Power BI Migration API...")

    # Ensure required folders exist
    config.ensure_directories()

    # Initialize SQLite/database tables
    init_database()

    logger.info(
        f"API started successfully on {config.API_HOST}:{config.API_PORT}"
    )

    yield

    logger.info("Shutting down ThoughtSpot -> Power BI Migration API...")


# ============================================================
# Create FastAPI App
# ============================================================

app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=config.API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ============================================================
# CORS Middleware
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=config.CORS_ALLOW_METHODS,
    allow_headers=config.CORS_ALLOW_HEADERS,
)


# ============================================================
# Root / Health Endpoints
# ============================================================

@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint.
    """

    return {
        "message": "ThoughtSpot to Power BI Migration API",
        "version": config.API_VERSION,
        "features": [
            "ThoughtSpot metadata upload",
            "ThoughtSpot TML parsing",
            "Worksheet and Liveboard analysis",
            "Formula to DAX conversion",
            "Relationship detection",
            "Power BI semantic model generation",
            "Power BI report output",
        ],
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint.
    """

    return {
        "status": "healthy",
        "service": "thoughtspot-powerbi-migration-api",
        "version": config.API_VERSION,
    }


# ============================================================
# Routers
# ============================================================

from api.routers import jobs, websocket, migration

app.include_router(
    jobs.router,
    prefix=f"{config.API_PREFIX}/jobs",
    tags=["jobs"],
)

app.include_router(
    websocket.router,
    prefix=f"{config.API_PREFIX}",
    tags=["websocket"],
)

app.include_router(
    migration.router,
    prefix=f"{config.API_PREFIX}/migration",
    tags=["migration"],
)


# ============================================================
# Global Exception Handler
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handle uncaught exceptions globally.
    """

    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "details": str(exc),
            }
        },
    )


# ============================================================
# Local Development Runner
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True,
        log_level="info",
    )
