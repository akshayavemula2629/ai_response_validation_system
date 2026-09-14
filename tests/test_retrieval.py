"""
Automated tests for Knowledge Base Semantic Retrieval (Test 9).
"""
import unittest
from backend.retrieval.retriever import retrieve_relevant_context
from backend.retrieval.vector_store import get_vector_store


class TestKnowledgeBaseRetrieval(unittest.TestCase):
    """Verifies independent semantic retrieval against indexed benchmark data."""

    @classmethod
    def setUpClass(cls):
        # Ensure index is loaded
        store = get_vector_store()
        if not store.is_ready():
            from backend.knowledge_base.ingestion import run_ingestion_pipeline
            run_ingestion_pipeline(max_samples=20, use_huggingface=False)

    def test_retrieval_query_moon_landing(self):
        """Test 9: Knowledge base retrieval for moon landing."""
        results = retrieve_relevant_context("Who was the first person to walk on the Moon?", top_k=2)
        self.assertGreaterEqual(len(results), 1)

        first_hit = results[0]
        self.assertTrue(hasattr(first_hit, "chunk_id"))
        self.assertTrue(hasattr(first_hit, "content"))
        self.assertTrue(hasattr(first_hit, "source"))
        self.assertTrue(hasattr(first_hit, "similarity_score"))
        self.assertGreater(first_hit.similarity_score, 0.3)
        self.assertTrue(
            "neil armstrong" in first_hit.content.lower() or "apollo" in first_hit.content.lower()
        )

    def test_retrieval_query_chewing_gum(self):
        """Knowledge base retrieval for swallowing chewing gum misconception."""
        results = retrieve_relevant_context("Does chewing gum stay in the stomach for seven years?", top_k=2)
        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(
            "chewing gum" in results[0].content.lower() or "digestive" in results[0].content.lower()
        )

    def test_empty_query_retrieval(self):
        """Empty query returns empty list."""
        results = retrieve_relevant_context("   ")
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
