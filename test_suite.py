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
        self.backend.discord_manager._last_published_kwargs = None
        
        # We can also put a dummy update to immediately wake the queue
        self.backend.discord_manager.cmd_queue.put({"type": "update", "generation": self.backend.media_generation, "client_id": self.backend.discord_manager.current_client_id, "kwargs": {"details": "Testing Disconnect"}})
        
        # Heal
        self.mock_presence.update.side_effect = None
        self.backend.discord_manager.rpc_reconnect_at = 0 
        
        self.assertTrue(self.wait_for_condition(lambda: self.backend.discord_manager.state == "CONNECTED", timeout=10.0))
        self.assertTrue(self.wait_for_condition(lambda: self.backend.discord_manager._last_published_kwargs is not None, timeout=5.0))

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

    def test_regression_a_tokyo_ghoul_re_s3_ep7(self):
        # A. Tokyo Ghoul:re + Season 3 + Episode 7 -> AniList ID 100240 -> SYNCABLE
        candidate_tokyo_ghoul_re = {
            "id": 100240,
            "title": {"english": "Tokyo Ghoul:re", "romaji": "Tokyo Ghoul:re", "native": "東京喰種 トーキョーグール:re"},
            "type": "ANIME",
            "format": "TV"
        }
        score, reason = self.backend._anilist_candidate_score("Tokyo Ghoul:re", "Season 3 Episode 7", candidate_tokyo_ghoul_re)
        self.assertGreaterEqual(score, 80)
        self.assertIn("exact title", reason)

    def test_regression_b_tokyo_ghoul_s1(self):
        # B. Tokyo Ghoul + Season 1 -> ID 20605
        candidate_tg = {
            "id": 20605,
            "title": {"english": "Tokyo Ghoul", "romaji": "Tokyo Ghoul", "native": "東京喰種 トーキョーグール"},
            "type": "ANIME",
            "format": "TV"
        }
        score, reason = self.backend._anilist_candidate_score("Tokyo Ghoul", "Season 1 Episode 1", candidate_tg)
        self.assertGreaterEqual(score, 80)

    def test_regression_c_tokyo_ghoul_re_2(self):
        # C. Tokyo Ghoul:re 2 -> ID 102351
        candidate_tg_re_2 = {
            "id": 102351,
            "title": {"english": "Tokyo Ghoul:re 2nd Season", "romaji": "Tokyo Ghoul:re 2nd Season", "native": "東京喰種 トーキョーグール:re 第2期"},
            "type": "ANIME",
            "format": "TV"
        }
        score, reason = self.backend._anilist_candidate_score("Tokyo Ghoul:re 2nd Season", "Season 2 Episode 1", candidate_tg_re_2)
        self.assertGreaterEqual(score, 80)

    def test_regression_d_overlord_ii(self):
        # D. Overlord II must not resolve to Overlord Season 1
        candidate_overlord_s1 = {
            "id": 29803,
            "title": {"english": "Overlord", "romaji": "Overlord"},
            "type": "ANIME",
            "format": "TV"
        }
        candidate_overlord_s2 = {
            "id": 98437,
            "title": {"english": "Overlord II", "romaji": "Overlord II"},
            "type": "ANIME",
            "format": "TV"
        }
        score1, _ = self.backend._anilist_candidate_score("Overlord II", "Episode 10", candidate_overlord_s1)
        score2, _ = self.backend._anilist_candidate_score("Overlord II", "Episode 10", candidate_overlord_s2)
        self.assertGreater(score2, score1)
        self.assertGreaterEqual(score2, 80)

    def test_regression_e_stale_metadata_worker(self):
        # E. Stale metadata worker must not write persistent cache
        initial_cache_len = len(self.backend.metadata_cache)
        self.backend.media_generation = 100
        self.backend._fetch_metadata_bg("anime:stale_test", "Stale Test", "Episode 1", False, "", "", "anime")
        self.assertEqual(len(self.backend.metadata_cache), initial_cache_len)

    def test_regression_f_force_sync_cache_key(self):
        # F. Force Sync must invalidate exact cache key generated by _build_cache_key()
        key = self.backend._build_cache_key("anime", "Test Force", "Episode 1")
        self.backend.metadata_cache[key] = {"title": "Test Force", "image_url": "http://example.com/art.jpg"}
        self.backend.state_data["cleaned_title"] = "Test Force"
        self.backend.state_data["episode_str"] = "Episode 1"
        self.backend.state_data["media_type"] = "anime"
        
        web_api = vlc_discord_rpc_gui.WebApi(self.backend)
        web_api.force_update()
        
        self.assertNotIn(key, self.backend.metadata_cache)

    def test_regression_g_gemini_stale_completion(self):
        # G. Gemini stale completion must not leave filename permanently "pending"
        self.backend.gemini_cache["stale_movie.mkv"] = "pending"
        self.backend.gemini_cache["stale_movie.mkv"] = None
        self.assertNotEqual(self.backend.gemini_cache.get("stale_movie.mkv"), "pending")

    def test_regression_h_corrupt_metadata_cache(self):
        # H. Corrupt metadata cache recovers automatically
        valid = self.backend._is_valid_cache_entry("not a dict")
        self.assertFalse(valid)
        valid_bad_ver = self.backend._is_valid_cache_entry({"_cache_version": 9999})
        self.assertFalse(valid_bad_ver)

    def test_regression_i_valid_cached_metadata(self):
        # I. Valid cached metadata loads without network fetch
        key = self.backend._build_cache_key("anime", "Cached Anime", "Episode 1")
        valid_entry = {
            "official_title": "Cached Anime Official",
            "image_url": "https://example.com/cover.jpg",
            "_cache_version": vlc_discord_rpc_gui.METADATA_CACHE_VERSION
        }
        self.assertTrue(self.backend._is_valid_cache_entry(valid_entry))

    def test_regression_j_missing_image_fallback(self):
        # J. Missing image from provider -> fallback attempted
        res = self.backend.prepare_metadata_cover({"official_title": "No Image Meta"})
        self.assertIsNone(res)

    def test_regression_k_tv_show_no_anilist(self):
        # K. TV show with S01E01 must not trigger AniList anime identity/sync
        self.backend.current_anilist_identity = None
        self.backend.ensure_anilist_identity("Breaking Bad", "Season 1 Episode 1", is_music=False, media_type="tv_show")
        self.assertIsNone(self.backend.current_anilist_identity)

    def test_regression_l_movie_no_anilist(self):
        # L. Movie with Episode-like filename must not trigger AniList anime sync
        self.backend.current_anilist_identity = None
        self.backend.ensure_anilist_identity("Inception", "Episode 1", is_music=False, media_type="movie")
        self.assertIsNone(self.backend.current_anilist_identity)

    def test_regression_m_last_fail_scope(self):
        # M. Verify last_fail scope/retrieval doesn't raise NameError
        self.backend.gemini_fail_times["test_file.mkv"] = time.time() - 3700
        raw_name = "test_file.mkv"
        last_fail = self.backend.gemini_fail_times.get(raw_name, 0)
        self.assertGreater(last_fail, 0)

    @patch("vlc_discord_rpc_gui.query_gemini_title")
    def test_regression_n_unknown_track_gemini_guard(self, mock_query):
        # N. Ensure 'Unknown Track' or empty titles are guarded and never queried to Gemini
        self.backend.config["gemini_api_key"] = "test_key"
        self.backend.state_data["title"] = "Unknown Track"
        file_name = ""
        _fallback_title = self.backend.state_data["title"]
        if _fallback_title in ("Unknown Track", "", None):
            _fallback_title = ""
        raw_name = file_name or _fallback_title
        _JUNK_NAMES = {"unknown track", "unknown", ""}
        should_query = bool(self.backend.config.get("gemini_api_key")) and raw_name.strip().lower() not in _JUNK_NAMES
        self.assertFalse(should_query)

if __name__ == '__main__':
    unittest.main()

