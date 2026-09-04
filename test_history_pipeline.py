import unittest
import os
import sqlite3
import tempfile
from vlc_discord_rpc_gui import VlcDiscordRpc

class MockConfig(dict):
    def get(self, k, default=None):
        return super().get(k, default)

class TestHistoryPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = VlcDiscordRpc()
        self.app.db_path = os.path.join(self.temp_dir.name, "history.db")
        self.app.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_history_priority_resolution(self):
        # Insert a dummy record with a DB cover
        conn = sqlite3.connect(self.app.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO history (title, episode_str, is_music, watch_duration, timestamp, cover_url) VALUES (?, ?, ?, ?, ?, ?)",
                  ("Test Anime", "1", 0, 100, "2024-01-01 12:00:00", "http://db-cover.png"))
        conn.commit()
        conn.close()
        
        # Test 1: DB cover is prioritized
        history_res = self.app.get_history()
        self.assertEqual(history_res["history"][0]["cover_url"], "http://db-cover.png")
        
        # Test 2: Cached cover fallback if DB is empty
        conn = sqlite3.connect(self.app.db_path)
        c = conn.cursor()
        c.execute("UPDATE history SET cover_url = '' WHERE title = 'Test Anime'")
        conn.commit()
        conn.close()
        
        self.app.metadata_cache = {"anime:Test Anime:1": {"title": "Test Anime", "image_url": "http://cached-cover.png"}}
        history_res = self.app.get_history()
        self.assertEqual(history_res["history"][0]["cover_url"], "http://cached-cover.png")

if __name__ == "__main__":
    unittest.main()
