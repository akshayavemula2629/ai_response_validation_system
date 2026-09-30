"""
Main FastAPI Application for AI Response Validation System.
Includes centralized exception handling, CORS middleware, router registration,
and OpenAPI documentation.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api.routes.health import router as health_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ai_response_validation_system")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting up %s (version %s)", settings.APP_NAME, settings.APP_VERSION)
    # Eagerly initialize embedding model if available to speed up first request
    try:
        from backend.retrieval.embeddings import get_embedding_manager
        logger.info("Pre-warming embedding model '%s'...", settings.EMBEDDING_MODEL_NAME)
        get_embedding_manager()
        logger.info("Embedding model pre-warmed successfully.")
    except Exception as e:
        logger.warning("Could not pre-warm embedding model on startup: %s", str(e))
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-quality backend for AI Response Validation System with Hallucination Detection Assistance. "
        "Provides automated evaluation of AI responses against reference answers and retrieved evidence "
        "across Relevance, Accuracy, Hallucination, and Completeness, with grounded better-answer generation."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Centralized validation error handler returning user-friendly error messages
    matching Milestone 1 specifications.
    """
    errors = exc.errors()
    error_title = "Validation Error"
    error_message = "Invalid submission payload."

    if errors:
        first_err = errors[0]
        msg = first_err.get("msg", "")
        loc = first_err.get("loc", [])
        field_name = loc[-1] if loc else "field"

        # Check if our custom validator message was raised
        if "Value error, " in msg:
            raw_msg = msg.replace("Value error, ", "")
            if ":" in raw_msg:
                parts = raw_msg.split(":", 1)
                error_title = parts[0].strip()
                error_message = parts[1].strip()
            else:
                error_message = raw_msg.strip()
                error_title = f"{str(field_name).replace('_', ' ').capitalize()} Error"
        elif first_err.get("type") == "missing":
            if "question" in str(field_name):
                error_title = "Question is required"
                error_message = "Please enter the question before submitting the evaluation."
            elif "reference_answer" in str(field_name):
                error_title = "Reference answer is required"
                error_message = "Please enter the reference answer before submitting the evaluation."
            elif "ai_response" in str(field_name):
                error_title = "AI response is required"
                error_message = "Please enter the AI response before submitting the evaluation."
            else:
                error_title = f"Missing field: {field_name}"
                error_message = f"Please provide a valid value for {field_name}."
        else:
            error_title = f"Invalid {field_name}"
            error_message = msg

    logger.warning("Validation failure on %s: %s - %s", request.url.path, error_title, error_message)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": error_title,
            "message": error_message
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Centralized catch-all exception handler to avoid leaking raw traces to clients.
    """
    logger.exception("Unhandled server exception on %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred while processing the evaluation. Please try again later."
        }
    )


# Include API routers
app.include_router(health_router, prefix="/api")

from backend.api.routes.evaluation import router as evaluation_router
app.include_router(evaluation_router, prefix="/api")
