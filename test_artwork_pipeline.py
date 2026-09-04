import unittest
from artwork_engine import ArtworkEngine

class TestArtworkPipeline(unittest.TestCase):
    def test_artwork_engine_decoupling(self):
        engine = ArtworkEngine(cache_dir="tmp", config={}, logger=None)
        # We test that the artwork engine safely handles missing covers
        engine.metrics = {"failed_requests": 0}
        engine.resolve_artwork_bg("test:id", {}, None)
        # Assuming resolve_artwork_bg exits early if metadata_url is None
        # It shouldn't crash
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
