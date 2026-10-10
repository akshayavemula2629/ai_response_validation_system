"""
Automated tests for semantic similarity calculations (Test 5).
Verifies embedding-based similarity percentage and explicit distinction from factual correctness.
"""
import unittest
from backend.evaluation.similarity import calculate_semantic_similarity


class TestSemanticSimilarity(unittest.TestCase):
    """Verifies embedding-based semantic similarity calculations."""

    def test_high_semantic_similarity(self):
        """Test 5: Semantically similar AI answer produces high similarity percentage."""
        ai_response = "The capital city of the Commonwealth of Australia is Canberra."
        reference_answer = "Canberra is the federal capital of Australia."

        result = calculate_semantic_similarity(ai_response, reference_answer)
        self.assertGreaterEqual(result.percentage, 80.0)
        self.assertLessEqual(result.percentage, 100.0)
        self.assertIn("similarity", result.explanation.lower())

    def test_divergent_semantic_similarity(self):
        """Divergent topics produce low semantic similarity."""
        ai_response = "Photosynthesis is the biological process used by plants to convert solar light into chemical energy."
        reference_answer = "The speed of light in a vacuum is 299,792,458 meters per second."

        result = calculate_semantic_similarity(ai_response, reference_answer)
        self.assertLess(result.percentage, 50.0)
        self.assertIn("low", result.explanation.lower())

    def test_similarity_distinction_from_correctness(self):
        """
        Confirms that similarity explanation explicitly clarifies that similarity
        does not guarantee factual correctness.
        """
        ai_response = "Neil Armstrong walked on Mars in 1985 during Apollo 11."
        reference_answer = "Neil Armstrong walked on the Moon on July 20, 1969 during Apollo 11."

        result = calculate_semantic_similarity(ai_response, reference_answer)
        # Structurally similar sentence syntax should yield moderate-to-high similarity
        self.assertGreater(result.percentage, 50.0)
        # But explanation must highlight that similarity is distinct from factual correctness
        self.assertIn("factual", result.explanation.lower())


if __name__ == "__main__":
    unittest.main()
