import unittest
import threading
import time
import os
import json
import sqlite3

# Mock Backend and Config
class MockConfig(dict):
    def get(self, key, default=None):
        return super().get(key, default)

class MockBackend:
    def __init__(self):
        self.config = MockConfig()
        self.CACHE_FILE = "test_cache.json"
        self._db_lock = threading.RLock()
        
    def init_db(self):
        self.db_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.db_conn.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY)")

# Import the class by parsing the file or assuming it's available in the same directory context
# For the sake of the test, we'll redefine a stub of DiagnosticsManager or import it if the sys path is right
import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from vlc_discord_rpc_gui import DiagnosticsManager

class TestDiagnosticsManager(unittest.TestCase):
    def setUp(self):
        self.backend = MockBackend()
        self.diagnostics = DiagnosticsManager(self.backend)
        
    def test_state_transitions(self):
        self.diagnostics.set_state("vlc", "HEALTHY", "Connected", is_success=True)
        state = self.diagnostics.get_state()
        self.assertEqual(state["components"]["vlc"]["state"], "HEALTHY")
        self.assertIsNotNone(state["components"]["vlc"]["last_success"])
        
        self.diagnostics.set_state("vlc", "OFFLINE", "Disconnected", is_failure=True)
        state = self.diagnostics.get_state()
        self.assertEqual(state["components"]["vlc"]["state"], "OFFLINE")
        self.assertIsNotNone(state["components"]["vlc"]["last_failure"])

    def test_error_aggregation(self):
        # Report the same error 5 times
        for _ in range(5):
            self.diagnostics.report_error("vlc", "TimeoutError", "Connection timed out")
            
        state = self.diagnostics.get_state()
        self.assertEqual(len(state["errors"]), 1)
        self.assertEqual(state["errors"][0]["count"], 5)
        
        # Report a different error
        self.diagnostics.report_error("vlc", "AuthError", "Invalid password")
        state = self.diagnostics.get_state()
        self.assertEqual(len(state["errors"]), 2)

    def test_concurrent_events(self):
        def worker():
            for i in range(100):
                self.diagnostics.log_event(f"Event {i}", "system")
                self.diagnostics.report_error("gemini", "TestError", "Test")
                
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        state = self.diagnostics.get_state()
        # Timeline bounded to 200
        self.assertEqual(len(state["timeline"]), 200)
        # 1 unique error reported 500 times
        self.assertEqual(len(state["errors"]), 1)
        self.assertEqual(state["errors"][0]["count"], 500)

    def test_export_sanitization(self):
        self.backend.config["gemini_api_key"] = "SUPER_SECRET_KEY"
        self.backend.config["vlc_password"] = "SECRET_PASS"
        self.backend.config["anilist_token"] = "SECRET_TOKEN"
        self.backend.config["normal_setting"] = True
        
        path = self.diagnostics.export_diagnostics()
        self.assertTrue(os.path.exists(path))
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.assertEqual(data["config"]["gemini_api_key"], "***REDACTED***")
        self.assertEqual(data["config"]["vlc_password"], "***REDACTED***")
        self.assertEqual(data["config"]["anilist_token"], "***REDACTED***")
        self.assertTrue(data["config"]["normal_setting"])
        
        os.remove(path)

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
