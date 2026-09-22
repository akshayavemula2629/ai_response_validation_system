"""
FAISS Vector Store for semantic search and evidence retrieval.
Manages vector indexing, persistent storage, and top-k nearest neighbor querying with metadata.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np
import faiss

from backend.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages FAISS index and corresponding chunk metadata."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStore, cls).__new__(cls)
            cls._instance._init_store()
        return cls._instance

    def _init_store(self):
        self.dimension = 384
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata: List[Dict[str, Any]] = []
        # Attempt to load existing index if present on disk
        if settings.VECTOR_INDEX_PATH.exists() and settings.METADATA_PATH.exists():
            self.load()

    def is_ready(self) -> bool:
        """Checks if index contains entries."""
        return self.index is not None and self.index.ntotal > 0 and len(self.metadata) > 0

    def count(self) -> int:
        """Returns the total number of indexed vectors."""
        return self.index.ntotal if self.index is not None else 0

    def add_documents(self, chunks: List[Dict[str, Any]], embeddings: np.ndarray):
        """
        Adds vector embeddings and associated metadata to the store.
        Embeddings must be shape (N, dimension) and float32.
        """
        if len(chunks) == 0 or len(embeddings) == 0:
            return

        embeddings = np.asarray(embeddings, dtype=np.float32)
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)

        dim = embeddings.shape[1]
        if self.index.d != dim:
            logger.info("Reinitializing index with dimension %d", dim)
            self.dimension = dim
            self.index = faiss.IndexFlatIP(dim)
            self.metadata = []

        # Ensure normalized vectors for cosine similarity via inner product
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        self.metadata.extend(chunks)
        logger.info("Added %d chunks to vector store. Total chunks: %d", len(chunks), self.index.ntotal)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 3,
        threshold: float = 0.0
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Searches the index for the nearest chunks.
        
        Returns:
            List of tuples: (chunk_metadata_dict, cosine_similarity_score).
        """
        if not self.is_ready():
            logger.warning("Vector store is empty. No evidence can be retrieved.")
            return []

        q_vec = np.asarray(query_embedding, dtype=np.float32)
        if len(q_vec.shape) == 1:
            q_vec = q_vec.reshape(1, -1)

        faiss.normalize_L2(q_vec)
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(q_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.metadata):
                similarity = float(score)
                if similarity >= threshold:
                    results.append((self.metadata[idx], similarity))

        return results

    def save(self, index_path: Path = None, metadata_path: Path = None):
        """Saves FAISS index and metadata to disk."""
        idx_path = index_path or settings.VECTOR_INDEX_PATH
        meta_path = metadata_path or settings.METADATA_PATH

        idx_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(idx_path))
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        logger.info("Successfully persisted vector index (%d items) to %s", self.index.ntotal, idx_path)

    def load(self, index_path: Path = None, metadata_path: Path = None) -> bool:
        """Loads FAISS index and metadata from disk."""
        idx_path = index_path or settings.VECTOR_INDEX_PATH
        meta_path = metadata_path or settings.METADATA_PATH

        if not idx_path.exists() or not meta_path.exists():
            logger.warning("Vector index or metadata file not found at %s", idx_path)
            return False

        try:
            self.index = faiss.read_index(str(idx_path))
            self.dimension = self.index.d
            with open(meta_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
            logger.info("Loaded vector index from %s (%d vectors, %d metadata entries)", idx_path, self.index.ntotal, len(self.metadata))
            return True
        except Exception as e:
            logger.error("Failed to load vector store from disk: %s", str(e))
            return False


def get_vector_store() -> VectorStore:
    """Returns the singleton VectorStore instance."""
    return VectorStore()
