"""
Embedding Manager and Vector Operations.
Provides singleton access to sentence-transformers models with fallback handling and caching.
"""
import logging
from typing import List, Union
import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Singleton manager for generating text embeddings and calculating vector similarities."""

    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
            cls._instance._initialize_model()
        return cls._instance

    def _initialize_model(self):
        """Initializes the SentenceTransformer model with fallback handling."""
        model_name = settings.EMBEDDING_MODEL_NAME
        logger.info("Initializing embedding model: %s", model_name)
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
            if hasattr(self._model, "get_embedding_dimension"):
                self._dim = self._model.get_embedding_dimension()
            else:
                self._dim = self._model.get_sentence_embedding_dimension()
            logger.info("SentenceTransformer '%s' loaded successfully. Embedding dimension: %d", model_name, self._dim)
        except Exception as e:
            logger.warning("Failed to load SentenceTransformer '%s' (%s). Initializing lightweight fallback.", model_name, str(e))
            self._model = None
            self._dim = 384

    @property
    def dimension(self) -> int:
        """Returns the embedding dimension."""
        return self._dim

    def embed_text(self, text: str) -> np.ndarray:
        """
        Embeds a single string into a 1D normalized float32 numpy array.
        """
        if not text or not text.strip():
            return np.zeros(self._dim, dtype=np.float32)

        if self._model is not None:
            emb = self._model.encode(text, normalize_embeddings=True, show_progress_bar=False)
            return np.array(emb, dtype=np.float32)
        else:
            # Fallback deterministic bag-of-words / char hash embedding for offline environments
            return self._fallback_embed([text])[0]

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Embeds a list of strings into a 2D normalized float32 numpy array (N, dim).
        """
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)

        cleaned_texts = [t if (t and t.strip()) else " " for t in texts]

        if self._model is not None:
            embs = self._model.encode(
                cleaned_texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            return np.array(embs, dtype=np.float32)
        else:
            return self._fallback_embed(cleaned_texts)

    def _fallback_embed(self, texts: List[str]) -> np.ndarray:
        """Deterministic hashing-based fallback vectorizer when neural model is unavailable."""
        from sklearn.feature_extraction.text import HashingVectorizer
        vectorizer = HashingVectorizer(n_features=self._dim, alternate_sign=False, norm='l2')
        matrix = vectorizer.transform(texts).toarray().astype(np.float32)
        return matrix

    @staticmethod
    def compute_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Computes cosine similarity between two 1D vectors or calculates dot product
        if vectors are already L2 normalized. Clamped between 0.0 and 1.0.
        """
        v1 = np.asarray(vec1, dtype=np.float32).flatten()
        v2 = np.asarray(vec2, dtype=np.float32).flatten()

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        similarity = float(np.dot(v1, v2) / (norm1 * norm2))
        # Clamp to [0.0, 1.0] for non-negative semantic similarity
        return max(0.0, min(1.0, similarity))


def get_embedding_manager() -> EmbeddingManager:
    """Returns the singleton EmbeddingManager instance."""
    return EmbeddingManager()
