import unittest
import os
import json
import time
from metadata_engine import MetadataEngine, MediaIdentity, MetadataResult

class TestMetadataEngine(unittest.TestCase):
    def setUp(self):
        self.cache_file = "test_metadata_cache.json"
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)

    def tearDown(self):
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)

    def test_parse_filename_simple(self):
        engine = MetadataEngine(cache_file=self.cache_file)
        identity = engine.parse_filename("Overlord II E10.mkv")
        self.assertEqual(identity.title, "Overlord II")
        self.assertEqual(identity.episode, 10)

    def test_parse_filename_complex(self):
        engine = MetadataEngine(cache_file=self.cache_file)
        identity = engine.parse_filename("[Erai-raws] ReZERO - Starting Life in Another World Season 2 E08 [1080p].mkv")
        self.assertIn("Re ZERO", identity.title)
        self.assertEqual(identity.episode, 8)

    def test_cache_migration(self):
        # Create legacy cache
        legacy_data = {
            "path:C:\\anime\\Overlord.mkv": {
                "title": "Overlord",
                "type": "anime",
                "image_url": "http://example.com/overlord.jpg",
                "anilistId": 123
            }
        }
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)
            
        engine = MetadataEngine(cache_file=self.cache_file)
        # Should have migrated
        self.assertIn("path:C:\\anime\\Overlord.mkv", engine.cache)
        res = engine.cache["path:C:\\anime\\Overlord.mkv"]
        self.assertEqual(res.recognition_method, "cache_migration")
        self.assertEqual(res.image_url, "http://example.com/overlord.jpg")
        
        # Verify persistence
        with open(self.cache_file, "r", encoding="utf-8") as f:
            persisted = json.load(f)
            self.assertIn("recognition_method", persisted["path:C:\\anime\\Overlord.mkv"])

    def test_dual_key_cache_lookup(self):
        engine = MetadataEngine(cache_file=self.cache_file)
        identity = MediaIdentity(title="Test Anime", episode=5, media_type="anime")
        res = MetadataResult(identity=identity, confidence=1.0)
        
        engine._cache_store(identity, res, file_path="C:\\anime\\test_05.mkv")
        
        # Look up by path
        hit1 = engine.resolve_sync(file_path="C:\\anime\\test_05.mkv", media_type_hint="anime")
        self.assertIsNotNone(hit1)
        self.assertTrue(hit1.cache_hit)
        
        # Look up by name (e.g. moved file)
        hit2 = engine.resolve_sync(file_path="D:\\new_path\\test_05.mkv", raw_title="Test Anime E05", media_type_hint="anime")
        self.assertIsNotNone(hit2)
        self.assertTrue(hit2.cache_hit)

    def test_negative_caching_and_deduplication(self):
        engine = MetadataEngine(cache_file=self.cache_file)
        
        # Inject an unresolved/failed lookup
        engine._set_negative_cache(engine._normalize_cache_key("Unknown Anime", None, 1, "anime"))
        
        future = engine.resolve_async(raw_title="Unknown Anime E01", media_type_hint="anime")
        res = future.result()
        
        # Should return immediately via negative cache
        self.assertEqual(res.recognition_method, "negative_cache")
        
        # Deduplication check
        future1 = engine.resolve_async(raw_title="Slow Resolve E01", media_type_hint="anime")
        future2 = engine.resolve_async(raw_title="Slow Resolve E01", media_type_hint="anime")
        self.assertIs(future1, future2)

    def test_stale_generation_protection(self):
        # We simulate the caller verifying the generation ID
        engine = MetadataEngine(cache_file=self.cache_file)
        
        # Mock the pipeline so it completes immediately
        def mock_pipeline(*args, **kwargs):
            return MetadataResult()
        engine._resolve_pipeline = mock_pipeline
        
        results = []
        def on_complete(res, gen):
            results.append(gen)
            
        f1 = engine.resolve_async(raw_title="Ep 10", generation=10, on_complete=on_complete)
        f1.result() # Wait
        self.assertIn(10, results)

if __name__ == "__main__":
    unittest.main()
