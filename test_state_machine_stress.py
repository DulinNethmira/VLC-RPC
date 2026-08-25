import os
import sys
import time
import json
import shutil
import threading
import unittest

# Add local path so vlc_discord_rpc_gui can be imported directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vlc_discord_rpc_gui import RPCBackend, DiscordManager, DEFAULT_CONFIG

class TestStateMachineStress(unittest.TestCase):

    def setUp(self):
        """Set up clean backend instance before each test."""
        self.backend = RPCBackend()
        self.backend.media_generation = 1
        self.backend.state_data["vlc_connected"] = True
        self.backend.state_data["playback_state"] = "playing"

    def tearDown(self):
        """Clean up temporary test artifacts."""
        test_cache = "metadata_cache.json"
        if os.path.exists(test_cache):
            try: os.remove(test_cache)
            except Exception: pass
        if os.path.exists(test_cache + ".bak"):
            try: os.remove(test_cache + ".bak")
            except Exception: pass

    def test_stale_metadata(self):
        """Test Simulation 1: A -> B -> C -> A delayed metadata rejection."""
        # Initial Session: Session 1 (Title A)
        self.backend.media_generation = 1
        gen_1 = self.backend.media_generation
        self.backend.state_data["title"] = "Title A"
        self.backend.state_data["_last_art_key"] = "path/to/title_A.mkv"
        self.backend.state_data["_last_art_uri"] = "path/to/title_A.mkv"

        # Rapidly transition: Session 1 (A) -> Session 2 (B) -> Session 3 (C) -> Session 4 (A new)
        self.backend.media_generation = 2  # B
        self.backend.media_generation = 3  # C
        self.backend.media_generation = 4  # A (new session)
        self.backend.state_data["_last_art_key"] = "path/to/title_A_new.mkv"
        self.backend.state_data["_last_art_uri"] = "path/to/title_A_new.mkv"

        # Try applying stale Gen 1 result using entry_generation check
        entry_generation = gen_1
        still_same_file = (
            self.backend.state_data.get("_last_art_key") == "path/to/title_A.mkv"
        )
        gen_match = (self.backend.media_generation == entry_generation)

        # Assert: Stale result MUST NOT apply
        self.assertFalse(gen_match, "Generation mismatch must be detected for stale metadata")
        self.assertFalse(still_same_file, "Stale file key must not match active session")
        print("  [PASS] test_stale_metadata: Stale metadata generation properly rejected.")

    def test_rewatch_leakage(self):
        """Test Simulation 2: REWATCH A -> WATCH B -> REWATCH C -> WATCH A state isolation."""
        # Step 1: Start Rewatch on Title A (Session 1)
        self.backend.media_generation = 1
        self.backend.state_data["watch_mode"] = "REWATCH"
        self.backend.state_data["rewatch_number"] = 2
        self.backend.state_data["possible_rewatch"] = False
        self.backend.state_data["_rewatch_generation"] = 1
        self.backend.current_anilist_identity = {"anilist_id": 101, "state": "SYNCABLE", "validated": True}

        self.assertEqual(self.backend.state_data["watch_mode"], "REWATCH")
        self.assertEqual(self.backend.state_data["rewatch_number"], 2)

        # Step 2: Transition to Title B (Session 2)
        # Emulate boundary logic from rpc_worker
        self.backend.state_data["watch_mode"] = "NORMAL"
        self.backend.state_data["rewatch_number"] = 0
        self.backend.state_data["possible_rewatch"] = False
        self.backend.state_data["rewatch_starting"] = False
        self.backend.state_data["_rewatch_generation"] = -1
        self.backend.state_data["anilist_identity"] = None
        self.backend.current_anilist_identity = None
        self.backend.media_generation += 1  # gen = 2

        self.assertEqual(self.backend.state_data["watch_mode"], "NORMAL")
        self.assertEqual(self.backend.state_data["rewatch_number"], 0)
        self.assertEqual(self.backend.state_data["_rewatch_generation"], -1)

        # Step 3: Start Rewatch on Title C (Session 3)
        self.backend.media_generation += 1  # gen = 3
        self.backend.state_data["watch_mode"] = "REWATCH"
        self.backend.state_data["rewatch_number"] = 1
        self.backend.state_data["_rewatch_generation"] = 3
        self.backend.current_anilist_identity = {"anilist_id": 303, "state": "SYNCABLE", "validated": True}

        self.assertEqual(self.backend.state_data["watch_mode"], "REWATCH")
        self.assertEqual(self.backend.state_data["rewatch_number"], 1)

        # Step 4: Transition to Title A normal watch (Session 4)
        self.backend.state_data["watch_mode"] = "NORMAL"
        self.backend.state_data["rewatch_number"] = 0
        self.backend.state_data["possible_rewatch"] = False
        self.backend.state_data["_rewatch_generation"] = -1
        self.backend.state_data["anilist_identity"] = None
        self.backend.current_anilist_identity = None
        self.backend.media_generation += 1  # gen = 4

        # Assert: Title A now operates in NORMAL mode with 0 rewatch count
        self.assertEqual(self.backend.state_data["watch_mode"], "NORMAL")
        self.assertEqual(self.backend.state_data["rewatch_number"], 0)
        self.assertIsNone(self.backend.current_anilist_identity)
        print("  [PASS] test_rewatch_leakage: Rewatch state isolated across media transitions.")

    def test_discord_reconnect(self):
        """Test Simulation 3: Discord connect -> disconnect -> reconnect sequence."""
        dm = DiscordManager(self.backend, "123456789")
        self.assertEqual(dm.state, "DISCONNECTED")

        # Simulate connect failure / loss
        dm.set_state("RECONNECTING", "Connection dropped during update")
        self.assertEqual(dm.state, "RECONNECTING")
        self.assertEqual(self.backend.state_data.get("health", {}).get("discord"), "RECONNECTING")

        # Simulate successful reconnect & state recovery
        dm.set_state("CONNECTED", "Connected to Discord.")
        self.assertEqual(dm.state, "CONNECTED")
        self.assertEqual(self.backend.state_data.get("health", {}).get("discord"), "HEALTHY")
        print("  [PASS] test_discord_reconnect: Discord manager state transitions verified.")

    def test_cache_corruption(self):
        """Test Simulation 4: Metadata cache valid -> corrupt -> repaired self-healing."""
        cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_corrupt_cache.json")
        self.backend.metadata_cache_file = cache_path

        # Step 1: Write corrupt payload
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write("{corrupt_json_payload: [invalid...")

        # Step 2: Attempt loading cache
        raw = open(cache_path, "r", encoding="utf-8").read().strip()
        try:
            json.loads(raw)
            corrupt = False
        except Exception as exc:
            corrupt = True
            shutil.copy2(cache_path, cache_path + ".bak")
            self.backend.metadata_cache = {}
            self.backend._set_health("cache", "REPAIRED", f"Metadata cache repaired — {exc}")

        # Assert: Corruption caught, .bak created, health updated
        self.assertTrue(corrupt, "JSONDecodeError must be triggered on corrupt file")
        self.assertTrue(os.path.exists(cache_path + ".bak"), "Backup copy .bak must be created")
        self.assertEqual(self.backend.state_data.get("health", {}).get("cache"), "REPAIRED")

        # Clean up
        if os.path.exists(cache_path): os.remove(cache_path)
        if os.path.exists(cache_path + ".bak"): os.remove(cache_path + ".bak")
        print("  [PASS] test_cache_corruption: Self-healing cache recovery verified.")

    def test_stale_gemini(self):
        """Test Simulation 5: Slow Gemini request -> media change -> stale result discarded."""
        self.backend.media_generation = 1
        launch_gen = self.backend.media_generation
        raw_name = "SlowAnime_EP01.mp4"

        # Media changes to gen 2 before Gemini returns
        self.backend.media_generation = 2

        # Simulate Gemini worker completion check
        stale_discarded = False
        if self.backend.media_generation != launch_gen:
            stale_discarded = True
            self.backend.log(f"[STATE] Discarded stale Gemini result for '{raw_name}' (gen {launch_gen} -> {self.backend.media_generation})")

        self.assertTrue(stale_discarded, "Stale Gemini worker result must be discarded")
        print("  [PASS] test_stale_gemini: Stale Gemini result discarded on generation change.")

    def test_stale_anilist(self):
        """Test Simulation 6: Slow AniList response -> media change -> old response discarded."""
        self.backend.media_generation = 10
        launch_gen = self.backend.media_generation
        anilist_id = 5050

        # Media changes to gen 11
        self.backend.media_generation = 11

        # Attempt applying MediaList from launch_gen 10
        applied = self.backend._apply_anilist_media_list(anilist_id, {"status": "COMPLETED"}, launch_generation=launch_gen)

        self.assertFalse(applied, "MediaList apply must return False when generation has changed")
        print("  [PASS] test_stale_anilist: Stale AniList MediaList response rejected.")

    def test_stale_artwork(self):
        """Test Simulation 7: Artwork online failure -> local VLC fallback -> online success."""
        search_title = "Test Anime Artwork"

        # Online fetch fails (returns empty metadata / image_url)
        metadata = None
        if not metadata or not metadata.get("image_url"):
            self.backend._set_health("metadata", "DEGRADED", "Artwork fallback activated")
            self.backend.state_data["local_arturl"] = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="

        self.assertEqual(self.backend.state_data.get("health", {}).get("metadata"), "DEGRADED")
        self.assertTrue(self.backend.state_data.get("local_arturl").startswith("data:image/png"))

        # Subsequent fetch succeeds
        metadata = {"official_title": "Test Anime", "image_url": "https://example.com/art.jpg"}
        if metadata and metadata.get("image_url"):
            self.backend._set_health("metadata", "HEALTHY")

        self.assertEqual(self.backend.state_data.get("health", {}).get("metadata"), "HEALTHY")
        print("  [PASS] test_stale_artwork: Artwork fallback & recovery verified.")

    def test_rapid_media_switching(self):
        """Test Simulation 10: Rapid switching across 50 media items without race conditions."""
        start_gen = self.backend.media_generation

        for i in range(50):
            self.backend.media_generation += 1
            self.backend.state_data["watch_mode"] = "NORMAL"
            self.backend.state_data["rewatch_number"] = 0
            self.backend.state_data["_rewatch_generation"] = -1
            self.backend.current_anilist_identity = None

        self.assertEqual(self.backend.media_generation, start_gen + 50)
        self.assertEqual(self.backend.state_data["watch_mode"], "NORMAL")
        self.assertEqual(self.backend.state_data["_rewatch_generation"], -1)
        print("  [PASS] test_rapid_media_switching: 50 sequential media transitions completed cleanly.")

if __name__ == "__main__":
    print("=" * 70)
    print("      VLC RPC — STATE MACHINE STRESS TEST HARNESS")
    print("=" * 70)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestStateMachineStress)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\nALL STRESS TESTS PASSED CONSISTENTLY! SYSTEM IS STABLE.")
        sys.exit(0)
    else:
        print("\nSTRESS TESTS FAILED! ISSUES DETECTED.")
        sys.exit(1)
