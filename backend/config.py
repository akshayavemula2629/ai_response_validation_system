"""
Configuration settings for the AI Response Validation System.
Centralizes environment variables, model identifiers, file paths, and scoring constants.
"""
from pathlib import Path
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Base project directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

class Settings:
    # Environment & Server
    APP_NAME: str = "AI Response Validation System"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("APP_DEBUG", "true").lower() in ("true", "1", "yes")
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # File storage paths
    RAW_DATA_PATH: Path = RAW_DATA_DIR
    PROCESSED_DATA_PATH: Path = PROCESSED_DATA_DIR
    VECTOR_INDEX_PATH: Path = Path(os.getenv("VECTOR_INDEX_PATH", str(PROCESSED_DATA_DIR / "vector_index.faiss")))
    METADATA_PATH: Path = Path(os.getenv("METADATA_PATH", str(PROCESSED_DATA_DIR / "metadata.json")))

    # Embedding & Retrieval
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "3"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.20"))

    # LLM Settings (Optional)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Evaluation Weights (Must sum to 1.0)
    WEIGHT_RELEVANCE: float = float(os.getenv("WEIGHT_RELEVANCE", "0.25"))
    WEIGHT_ACCURACY: float = float(os.getenv("WEIGHT_ACCURACY", "0.35"))
    WEIGHT_HALLUCINATION: float = float(os.getenv("WEIGHT_HALLUCINATION", "0.25"))
    WEIGHT_COMPLETENESS: float = float(os.getenv("WEIGHT_COMPLETENESS", "0.15"))

    # Verdict Score Thresholds
    EXCELLENT_THRESHOLD: float = 85.0
    GOOD_THRESHOLD: float = 70.0
    NEEDS_IMPROVEMENT_THRESHOLD: float = 50.0

    # Hallucination Risk Thresholds
    HALLUCINATION_LOW_MAX: float = 20.0
    HALLUCINATION_MED_MAX: float = 50.0

settings = Settings()
