import unittest
from unittest.mock import patch, MagicMock
import time
import json
import threading
import copy

import vlc_discord_rpc_gui

class BaseIntegrationTest(unittest.TestCase):
    def setUp(self):
        # Mocks
        self.mock_window = MagicMock()
        vlc_discord_rpc_gui._notifier_client = MagicMock()
        
        self.presence_patcher = patch('vlc_discord_rpc_gui.Presence')
        self.mock_presence_class = self.presence_patcher.start()
        self.mock_presence = MagicMock()
        self.mock_presence_class.return_value = self.mock_presence
        
        self.requests_get_patcher = patch('vlc_discord_rpc_gui.requests.get')
        self.mock_requests_get = self.requests_get_patcher.start()
        
        self.requests_post_patcher = patch('vlc_discord_rpc_gui.requests.post')
        self.mock_requests_post = self.requests_post_patcher.start()
        
        self.set_vlc_state("stopped")
        
        # Initialize Backend
        self.backend = vlc_discord_rpc_gui.RPCBackend()
        self.backend.window = self.mock_window
        self.backend.config["update_interval"] = 0.1 # Very fast polling for tests
        self.backend.config["vlc_port"] = 8080
        
        # We need to speed up DiscordManager's queue pulling
        # but it uses timeout=1.0. We can't change it easily, but 1s is fine.
        
    def tearDown(self):
        self.backend.state_data["exit_flag"] = True
        self.backend.discord_manager.stop()
        if hasattr(self.backend, 'worker_thread'):
            self.backend.worker_thread.join(timeout=2.0)
            
        self.presence_patcher.stop()
        self.requests_get_patcher.stop()
        self.requests_post_patcher.stop()

    def set_vlc_state(self, state="stopped", time=0, length=0, filename="", url=""):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "state": state,
            "time": time,
            "length": length,
            "information": {
                "category": {
                    "meta": {
                        "filename": filename,
                        "url": url,
                        "title": ""
                    }
                }
            }
        }
        self.mock_requests_get.return_value = mock_resp

    def wait_for_condition(self, condition_func, timeout=5.0):
        start = time.time()
        while time.time() - start < timeout:
            if condition_func():
                return True
            time.sleep(0.05)
        return False

class TestScenarios(BaseIntegrationTest):

    def test_01_app_startup_discord_not_running(self):
        # Scenario 1: App startup — Discord not running -> Reconnecting loop, no crash
        self.mock_presence.connect.side_effect = Exception("Discord not running")
        self.set_vlc_state()
        time.sleep(0.5)
        self.assertIn(self.backend.discord_manager.state, ["RECONNECTING", "CONNECTING"])

    def test_02_app_startup_discord_already_running(self):
        # Scenario 2: App startup — Discord already running -> Connects immediately
        self.mock_presence.connect.return_value = None
        self.set_vlc_state()
        
        self.assertTrue(self.wait_for_condition(lambda: self.backend.discord_manager.state == "CONNECTED"))

    def test_04_discord_killed_mid_playback(self):
        # Scenario 4: Discord killed mid-playback -> Reconnects, re-publishes current media
        self.mock_presence.connect.return_value = None
        self.set_vlc_state(state="playing", filename="Test Anime E01.mkv", url="file:///test1.mkv")
        
        self.assertTrue(self.wait_for_condition(lambda: self.backend.discord_manager.state == "CONNECTED"))
        self.assertTrue(self.wait_for_condition(lambda: self.mock_presence.update.called))
        
        # Simulate Discord disconnect
        self.mock_presence.update.side_effect = Exception("Pipe broken")
        self.backend.discord_manager.last_update_time -= 20  # Force update
        
        # We can also put a dummy update to immediately wake the queue
        self.backend.discord_manager.cmd_queue.put({"type": "update", "generation": self.backend.media_generation, "client_id": self.backend.discord_manager.current_client_id, "kwargs": {}})
        
        # Next poll cycle will fail to update and transition to RECONNECTING
        self.assertTrue(self.wait_for_condition(lambda: self.backend.discord_manager.state == "RECONNECTING", timeout=10.0))
        
        # Heal
        self.mock_presence.update.side_effect = None
        # Discard old reconnect backoff for testing speed
        self.backend.discord_manager.rpc_reconnect_at = 0 
        
        self.assertTrue(self.wait_for_condition(lambda: self.backend.discord_manager.state == "CONNECTED", timeout=10.0))
        
        # Check it republished
        # It should call update again. Let's reset mock to be sure.
        self.mock_presence.update.reset_mock()
        self.backend.discord_manager.last_update_time = 0
        self.backend.discord_manager.cmd_queue.put({"type": "update", "generation": self.backend.media_generation, "client_id": self.backend.discord_manager.current_client_id, "kwargs": self.backend.discord_manager.current_kwargs})
        
        self.assertTrue(self.wait_for_condition(lambda: self.mock_presence.update.called, timeout=10.0))

    def test_07_vlc_killed_mid_playback(self):
        # Scenario 7: VLC killed mid-playback -> Disconnected state, Discord clears
        self.mock_presence.connect.return_value = None
        self.set_vlc_state(state="playing", filename="Test Anime E01.mkv", url="file:///test1.mkv")
        self.assertTrue(self.wait_for_condition(lambda: self.backend.state_data["vlc_connected"]))
        self.assertTrue(self.wait_for_condition(lambda: self.mock_presence.update.called))
        
        # Kill VLC
        self.mock_requests_get.side_effect = vlc_discord_rpc_gui.requests.exceptions.RequestException("Connection refused")
        
        self.assertTrue(self.wait_for_condition(lambda: not self.backend.state_data["vlc_connected"]))
        self.assertTrue(self.wait_for_condition(lambda: self.mock_presence.clear.called))

    def test_08_anime_a_to_anime_b(self):
        # Scenario 8: Anime A -> Anime B -> Fresh metadata, new generation
        self.mock_presence.connect.return_value = None
        self.set_vlc_state(state="playing", filename="Anime A E01.mkv", url="file:///a.mkv")
        self.assertTrue(self.wait_for_condition(lambda: self.backend.state_data.get("title") == "Anime A E01"))
        gen_a = self.backend.media_generation
        
        self.set_vlc_state(state="playing", filename="Anime B E01.mkv", url="file:///b.mkv")
        self.assertTrue(self.wait_for_condition(lambda: self.backend.state_data.get("title") == "Anime B E01"))
        gen_b = self.backend.media_generation
        
        self.assertGreater(gen_b, gen_a)

    def test_12_rapid_media_transitions(self):
        # Scenario 12: Rapid media transitions -> Only last media's metadata applies
        self.mock_presence.connect.return_value = None
        
        # We need to simulate slow metadata fetch for Anime A
        def slow_anilist(*args, **kwargs):
            time.sleep(1)
            return {"official_title": "Anime A Official"}
            
        with patch.object(self.backend, 'fetch_anilist_metadata', side_effect=slow_anilist):
            self.set_vlc_state(state="playing", filename="Anime A E01.mkv", url="file:///a.mkv")
            time.sleep(0.1) # Let worker spawn thread A
            
            self.set_vlc_state(state="playing", filename="Anime B E01.mkv", url="file:///b.mkv")
            self.assertTrue(self.wait_for_condition(lambda: self.backend.state_data.get("title") == "Anime B E01"))
            
            # Wait for A's slow thread to finish
            time.sleep(1.2) 
            
            # Ensure Anime A's metadata was NOT applied
            meta = self.backend.state_data.get("metadata") or {}
            self.assertNotEqual(meta.get("official_title"), "Anime A Official")

    def test_13_title_with_special_chars(self):
        # Scenario 13: Title with special chars (Steins;Gate) -> Preserved exactly
        res = vlc_discord_rpc_gui.clean_title("Steins;Gate Episode 1.mkv")
        self.assertEqual(res["title"], "Steins;Gate")
        self.assertEqual(res["episode"], 1)

    def test_14_title_with_year(self):
        # Scenario 14: Title with year (Hunter x Hunter 1999)
        res = vlc_discord_rpc_gui.clean_title("Hunter x Hunter 1999 Episode 1.mkv")
        self.assertEqual(res["title"], "Hunter x Hunter (1999)")

    def test_rewatch_to_normal(self):
        # Test exact REWATCH -> NORMAL transition
        self.backend.state_data["watch_mode"] = "REWATCH"
        self.backend.state_data["rewatch_number"] = 2
        self.backend.state_data["_rewatch_generation"] = self.backend.media_generation
        
        # Now change media
        self.set_vlc_state(state="playing", filename="Different Anime E01.mkv", url="file:///diff.mkv")
        
        # Generation should increment, and mode should drop to NORMAL
        self.assertTrue(self.wait_for_condition(lambda: self.backend.state_data["watch_mode"] == "NORMAL"))
        self.assertEqual(self.backend.state_data["rewatch_number"], 0)

if __name__ == '__main__':
    unittest.main()
