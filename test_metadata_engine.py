import unittest
from metadata_engine import MetadataEngine, MediaIdentity, MetadataResult
import time

class TestMetadataEngineFull(unittest.TestCase):
    def setUp(self):
        self.engine = MetadataEngine()
        
    def test_artwork_failure_preserves_metadata(self):
        # Even if artwork fails, it should preserve the metadata and not return confidence=0.0
        identity = MediaIdentity(title="Test Anime", filename="Test Anime.mkv", media_type="anime")
        
        # We can mock fetch_anilist_metadata to return data without an image_url
        def mock_fetch(title):
            return {
                "anilistId": 12345,
                "title": {"romaji": "Test Anime"},
                "image_url": None, # Fails!
                "genres": ["Action"],
                "rating": 80
            }
        self.engine.fetch_anilist_metadata = mock_fetch
        
        # Also mock gemini out
        self.engine.query_gemini = lambda f, k: None
        
        res = self.engine._resolve_pipeline(identity, gemini_api_key="")
        
        # Decoupling fix: Result should still have confidence > 0 and be verified.
        self.assertEqual(res.verification_status, "verified")
        self.assertEqual(res.anilist_id, 12345)
        self.assertIsNone(res.image_url)
        self.assertEqual(res.confidence, 0.85)

if __name__ == "__main__":
    unittest.main()
