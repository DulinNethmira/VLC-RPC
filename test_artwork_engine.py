import os
import time
import json
import shutil
import unittest
import tempfile
import threading
from unittest.mock import patch, MagicMock

from artwork_engine import ArtworkEngine, ArtworkResult

class TestArtworkEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {"vlc_host": "localhost", "vlc_port": 8080, "vlc_password": ""}
        
        # Mock Logger
        self.mock_logger = MagicMock()
        
        self.engine = ArtworkEngine(self.temp_dir, self.config, self.mock_logger)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_initialization(self):
        self.assertTrue(os.path.exists(self.temp_dir))
        self.assertEqual(len(self.engine.cache_index), 0)

    @patch('requests.get')
    def test_remote_artwork_download_and_validation(self, mock_get):
        # Mock successful download of a valid fake image (GIF header)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "image/jpeg", "Content-Length": "100"}
        mock_resp.iter_content.return_value = [b"GIF89a", b"fake_data"]
        mock_get.return_value = mock_resp

        # Trigger background resolution
        self.engine.resolve_artwork_bg("remote_test", {}, "https://s4.anilist.co/file/test.jpg")
        
        # Wait for thread to complete
        time.sleep(0.1)

        result = self.engine.resolve_artwork_fast("remote_test")
        self.assertIsNotNone(result)
        self.assertEqual(result.source, "REMOTE")
        self.assertEqual(result.validation_status, "VALID")
        self.assertEqual(result.discord_url, "https://s4.anilist.co/file/test.jpg")
        
    @patch('requests.get')
    def test_invalid_image_response(self, mock_get):
        # Mock successful download but NOT an image (HTML)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "image/jpeg", "Content-Length": "100"}
        mock_resp.iter_content.return_value = [b"<html>not an image</html>"]
        mock_get.return_value = mock_resp

        self.engine.resolve_artwork_bg("invalid_test", {}, "https://s4.anilist.co/file/test2.jpg")
        time.sleep(0.1)

        result = self.engine.resolve_artwork_fast("invalid_test")
        self.assertIsNone(result) # Should not cache invalid images

    def test_embedded_local_artwork(self):
        # Create a fake local valid image file
        fake_img_path = os.path.join(self.temp_dir, "cover.jpg")
        with open(fake_img_path, "wb") as f:
            f.write(b"GIF89a_fake")
            
        vlc_data = {"artwork_url": f"file:///{fake_img_path}"}
        
        with patch.object(self.engine, '_get_or_upload_imgur', return_value="https://i.imgur.com/test.jpg"):
            self.engine.resolve_artwork_bg("local_test", vlc_data)
            time.sleep(0.1)
            
            result = self.engine.resolve_artwork_fast("local_test")
            self.assertIsNotNone(result)
            self.assertEqual(result.source, "EMBEDDED")
            self.assertEqual(result.discord_url, "https://i.imgur.com/test.jpg")

    def test_duplicate_concurrent_requests_deduplication(self):
        # Ensure only one thread is spawned for identical keys
        vlc_data = {"artwork_url": ""}
        
        with patch.object(self.engine, '_do_resolve') as mock_resolve:
            mock_resolve.return_value = None
            
            # Call twice instantly
            self.engine.resolve_artwork_bg("dedup_test", vlc_data)
            self.engine.resolve_artwork_bg("dedup_test", vlc_data)
            
            # One thread is in flight
            self.assertIn("dedup_test", self.engine.in_flight_tasks)
            
            time.sleep(0.1)
            
            # _do_resolve should only have been called ONCE due to lock and in-flight tracking
            mock_resolve.assert_called_once()

    def test_bounded_cache_cleanup(self):
        # Populate cache with 201 items
        for i in range(205):
            self.engine.cache_index[f"test_{i}"] = {
                "source": "CACHE",
                "local_path": f"/fake/path/{i}.jpg",
                "last_used": time.time() + i
            }
            
        self.engine._enforce_cache_limits(max_items=200)
        self.assertEqual(len(self.engine.cache_index), 200)

if __name__ == '__main__':
    unittest.main()
