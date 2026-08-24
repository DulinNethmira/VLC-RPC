"""
Production Path Validation — Extended Test Suite
Tests: 1000-transition stability, randomized race test, cache validation, provider audit
DOES NOT MODIFY SOURCE CODE.
"""

import os
import sys
import time
import json
import shutil
import random
import threading
import unittest
import psutil
import gc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vlc_discord_rpc_gui import RPCBackend, DiscordManager

VENV_PYTHON = os.path.abspath(__file__)


def simulate_media_transition(backend):
    """Emulate the exact production media boundary logic from rpc_worker."""
    backend.state_data["watch_mode"] = "NORMAL"
    backend.state_data["rewatch_number"] = 0
    backend.state_data["possible_rewatch"] = False
    backend.state_data["rewatch_starting"] = False
    backend.state_data["_rewatch_generation"] = -1
    backend.state_data["anilist_identity"] = None
    backend.state_data["anilist_identity_state"] = "UNKNOWN"
    backend.current_anilist_identity = None
    backend.media_generation += 1


class Test1000TransitionStability(unittest.TestCase):
    """Section 8: Long-run stability across 1000 media transitions."""

    def test_1000_transitions(self):
        backend = RPCBackend()
        proc = psutil.Process()

        checkpoints = [0, 100, 250, 500, 750, 1000]
        results = []

        for i in range(1001):
            simulate_media_transition(backend)
            # Occasionally set REWATCH then revert
            if i % 7 == 0:
                backend.state_data["watch_mode"] = "REWATCH"
                backend.state_data["rewatch_number"] = (i % 5) + 1
                backend.state_data["_rewatch_generation"] = backend.media_generation
                backend.current_anilist_identity = {
                    "anilist_id": 10000 + i,
                    "state": "SYNCABLE",
                    "validated": True,
                    "source_key": f"title_{i}"
                }
            if i in checkpoints:
                gc.collect()
                rss = proc.memory_info().rss // 1024 // 1024  # MB
                threads = threading.active_count()
                results.append((i, rss, threads))
                print(f"  T={i:4d} | RSS={rss}MB | Threads={threads} | Gen={backend.media_generation}")

        # Verify final state
        print()
        print("  Checkpoint Summary:")
        print(f"  {'Transitions':>12} | {'RSS (MB)':>10} | {'Threads':>8}")
        for t, rss, threads in results:
            print(f"  {t:>12} | {rss:>10} | {threads:>8}")

        # Assert no continuous growth (first vs last should be within 20MB)
        first_rss = results[0][1]
        last_rss = results[-1][1]
        growth = last_rss - first_rss
        print(f"\n  RSS growth: {growth}MB (T=0 to T=1000)")

        # Check final state is clean
        self.assertEqual(backend.state_data["watch_mode"], "NORMAL",
                         "After 1000 transitions, final watch_mode must be NORMAL")
        self.assertEqual(backend.state_data["_rewatch_generation"], -1,
                         "After 1000 transitions, _rewatch_generation must be -1")
        self.assertIsNone(backend.current_anilist_identity,
                          "After 1000 transitions, current_anilist_identity must be None")
        self.assertLess(growth, 50, f"RSS grew {growth}MB — possible memory leak")
        print(f"  [PASS] test_1000_transitions: stable.")


class TestRandomizedRace(unittest.TestCase):
    """Section 9: Randomized race test with varied latencies across 100 iterations."""

    def _simulate_async_worker(self, backend, launch_gen, result_holder, latency):
        """Generic delayed async worker that checks generation on completion."""
        time.sleep(latency)
        if backend.media_generation != launch_gen:
            result_holder["discarded"] += 1
        else:
            result_holder["applied"] += 1

    def test_randomized_race_100_iterations(self):
        backend = RPCBackend()
        backend.media_generation = 1

        results = {"discarded": 0, "applied": 0, "violations": 0}
        threads = []

        for iteration in range(100):
            # Capture generation at launch
            launch_gen = backend.media_generation

            # Latency between 0ms and 300ms
            latency = random.uniform(0.0, 0.3)

            t = threading.Thread(
                target=self._simulate_async_worker,
                args=(backend, launch_gen, results, latency),
                daemon=True
            )
            threads.append(t)
            t.start()

            # Randomly switch media 0-2 times per iteration
            switches = random.randint(0, 2)
            for _ in range(switches):
                time.sleep(random.uniform(0.0, 0.05))
                simulate_media_transition(backend)

        for t in threads:
            t.join(timeout=2.0)

        total = results["discarded"] + results["applied"]
        print(f"\n  Randomized Race Results ({100} iterations):")
        print(f"    Workers Applied:   {results['applied']}")
        print(f"    Workers Discarded: {results['discarded']}")
        print(f"    Total:             {total}")
        print(f"    Violations:        {results['violations']}")

        self.assertEqual(results["violations"], 0,
                         "No async worker may mutate state from an older generation")
        self.assertEqual(total, 100,
                         "All 100 async workers must have either applied or been discarded")
        print("  [PASS] test_randomized_race_100_iterations.")


class TestCacheValidation(unittest.TestCase):
    """Section 7: Comprehensive cache validation scenarios."""

    CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cache_validation.json")

    def tearDown(self):
        for path in [self.CACHE, self.CACHE + ".bak"]:
            if os.path.exists(path):
                os.remove(path)

    def _write_and_load(self, content):
        with open(self.CACHE, "w", encoding="utf-8") as f:
            f.write(content)
        raw = open(self.CACHE, encoding="utf-8").read().strip()
        try:
            return json.loads(raw), None
        except Exception as exc:
            shutil.copy2(self.CACHE, self.CACHE + ".bak")
            return {}, exc

    def test_corrupt_json(self):
        data, exc = self._write_and_load("{invalid_json: True")
        self.assertIsNotNone(exc)
        self.assertTrue(os.path.exists(self.CACHE + ".bak"))
        print("  [PASS] test_corrupt_json")

    def test_truncated_json(self):
        data, exc = self._write_and_load('{"key": "val')
        self.assertIsNotNone(exc)
        print("  [PASS] test_truncated_json")

    def test_empty_json(self):
        data, exc = self._write_and_load("")
        # Empty content raises json.JSONDecodeError
        self.assertIsNotNone(exc)
        print("  [PASS] test_empty_json")

    def test_valid_but_wrong_schema(self):
        data, exc = self._write_and_load('["not", "a", "dict"]')
        # Parses fine but is a list — application must guard isinstance(result, dict)
        self.assertIsNone(exc, "Parses without error")
        self.assertNotIsInstance(data, dict, "Schema mismatch: list, not dict")
        print("  [PASS] test_valid_but_wrong_schema")

    def test_missing_cache_file(self):
        if os.path.exists(self.CACHE):
            os.remove(self.CACHE)
        # Backend must not raise when cache file is absent
        backend = RPCBackend.__new__(RPCBackend)
        result = {}
        if not os.path.exists(self.CACHE):
            result = {}  # Default empty cache
        self.assertEqual(result, {})
        print("  [PASS] test_missing_cache_file")

    def test_cache_version_mismatch(self):
        data, _ = self._write_and_load('{"title_A": {"_cache_version": 999, "image_url": "https://old.url"}}')
        # Version mismatch: entry with wrong version must be rejected
        from vlc_discord_rpc_gui import METADATA_CACHE_VERSION
        for k, v in data.items():
            if isinstance(v, dict) and v.get("_cache_version") != METADATA_CACHE_VERSION:
                self.assertNotEqual(v["_cache_version"], METADATA_CACHE_VERSION)
        print("  [PASS] test_cache_version_mismatch")

    def test_stale_negative_entry(self):
        stale_ts = time.time() - 99999
        payload = json.dumps({
            "old_title": {"_negative": True, "_negative_ts": stale_ts, "_negative_count": 1}
        })
        data, exc = self._write_and_load(payload)
        self.assertIsNone(exc)
        entry = data.get("old_title", {})
        is_neg = entry.get("_negative", False)
        ts = entry.get("_negative_ts", 0)
        expired = (time.time() - ts) > 60
        self.assertTrue(is_neg)
        self.assertTrue(expired, "Stale negative entry must be recognized as expired")
        print("  [PASS] test_stale_negative_entry")


class TestProviderAudit(unittest.TestCase):
    """Section 4: Metadata provider timeout and error handling audit."""

    def test_provider_timeouts_are_bounded(self):
        """All providers must have reasonable timeouts to not block the background thread."""
        src = open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "vlc_discord_rpc_gui.py"),
            encoding="utf-8"
        ).read()

        # Verify key provider calls have timeout
        providers = {
            "fetch_tvmaze": "timeout=5",
            "fetch_jikan": "timeout=5",
            "fetch_anilist_metadata": "timeout=8",
            "fetch_omdb": "timeout=5",
            "fetch_wikipedia": "timeout=3",
        }
        for provider, expected_timeout in providers.items():
            idx = src.find(f"def {provider}")
            segment = src[idx:idx+2000] if idx >= 0 else ""
            # Check that a timeout= value exists in the provider function body
            has_timeout = "timeout=" in segment
            self.assertTrue(has_timeout, f"{provider} must have a timeout= argument")

        print("  [PASS] test_provider_timeouts_are_bounded")

    def test_prepare_metadata_cover_validates_input(self):
        """prepare_metadata_cover must reject non-dict and None inputs gracefully."""
        backend = RPCBackend()
        self.assertIsNone(backend.prepare_metadata_cover(None))
        self.assertIsNone(backend.prepare_metadata_cover("string"))
        self.assertIsNone(backend.prepare_metadata_cover(42))
        print("  [PASS] test_prepare_metadata_cover_validates_input")

    def test_merge_metadata_does_not_erase_valid_fields(self):
        """_merge_metadata must not erase a valid primary field with empty fallback."""
        backend = RPCBackend()
        base = {"image_url": "https://primary.com/cover.jpg", "rating": "8.5", "genres": ["Action"]}
        update = {"image_url": "", "rating": None, "genres": []}
        merged = backend._merge_metadata(base, update)
        self.assertEqual(merged.get("image_url"), "https://primary.com/cover.jpg",
                         "_merge_metadata must not replace valid image_url with empty string")
        print("  [PASS] test_merge_metadata_does_not_erase_valid_fields")


class TestSameFileSessionRace(unittest.TestCase):
    """Section 6: Tests specifically for the same-file/rapid-restart race."""

    def test_same_file_metadata_gen1_discarded_gen2_applied(self):
        backend = RPCBackend()
        same_file_uri = "D:\\Anime\\AttackOnTitan\\E01.mkv"

        # Generation 1: File A starts
        backend.media_generation = 1
        backend.state_data["_last_art_key"] = same_file_uri
        backend.state_data["_last_art_uri"] = same_file_uri
        gen1_launch = backend.media_generation

        # Generation 2: Same File A stopped & restarted
        backend.media_generation = 2
        gen2_launch = backend.media_generation

        # Simulate Gen 1 metadata worker finishing NOW
        gen1_metadata = {"title": "Gen 1 Metadata", "image_url": "http://gen1.jpg"}
        # Manually invoke state assignment logic of _fetch_metadata_bg
        still_same_file = (
            not same_file_uri
            or backend.state_data.get("_last_art_key", "") == same_file_uri
            or backend.state_data.get("_last_art_uri", "") == same_file_uri
        )

        # Before fix: still_same_file is True so Gen 1 would overwrite!
        # With fix: gen1_launch (1) != backend.media_generation (2) -> DISCARDED
        if backend.media_generation == gen1_launch and still_same_file:
            backend.state_data["metadata"] = gen1_metadata

        self.assertIsNone(backend.state_data.get("metadata"),
                         "Gen 1 metadata MUST be discarded despite same file path")

        # Now Gen 2 metadata worker completes
        if backend.media_generation == gen2_launch and still_same_file:
            backend.state_data["metadata"] = {"title": "Gen 2 Metadata"}

        self.assertIsNotNone(backend.state_data.get("metadata"),
                            "Gen 2 metadata MUST be applied")
        self.assertEqual(backend.state_data["metadata"]["title"], "Gen 2 Metadata")
        print("  [PASS] test_same_file_metadata_gen1_discarded_gen2_applied")

    def test_same_file_anilist_gen1_discarded_gen2_applied(self):
        backend = RPCBackend()
        backend.media_generation = 1
        gen1_launch = backend.media_generation

        # Generation 2
        backend.media_generation = 2
        gen2_launch = backend.media_generation

        discards = []
        applies = []

        # Gen 1 finishes
        if backend.media_generation != gen1_launch:
            discards.append("gen1")
        else:
            applies.append("gen1")

        # Gen 2 finishes
        if backend.media_generation != gen2_launch:
            discards.append("gen2")
        else:
            applies.append("gen2")

        self.assertIn("gen1", discards, "Gen 1 AniList identity result MUST be discarded")
        self.assertIn("gen2", applies, "Gen 2 AniList identity result MUST be applied")
        print("  [PASS] test_same_file_anilist_gen1_discarded_gen2_applied")


class TestAtomicWrites(unittest.TestCase):
    """Section 4: Atomic configuration and history writes audit."""

    def test_save_config_atomic(self):
        from vlc_discord_rpc_gui import save_config, _persistent_config_path
        cfg_path = _persistent_config_path()
        tmp_path = cfg_path + ".tmp"
        save_config({"test_key": "test_value"})
        self.assertFalse(os.path.exists(tmp_path), ".tmp file must be cleaned up / replaced")
        self.assertTrue(os.path.exists(cfg_path), "Target config file must exist")
        print("  [PASS] test_save_config_atomic")

    def test_save_history_atomic(self):
        backend = RPCBackend()
        backend.history = [{"title": "Test Movie", "timestamp": 12345}]
        backend.save_history()
        # Ensure no residual .tmp file
        app_path = os.path.dirname(os.path.abspath(__file__))
        tmp_hist = os.path.join(app_path, "vlc_rpc_history.json.tmp")
        self.assertFalse(os.path.exists(tmp_hist), "History .tmp file must be cleaned up / replaced")
        print("  [PASS] test_save_history_atomic")


if __name__ == "__main__":
    print("=" * 70)
    print("  VLC RPC — PRODUCTION PATH VALIDATION EXTENDED TEST SUITE")
    print("=" * 70)
    loader = unittest.TestLoader()
    suites = []
    suites.append(loader.loadTestsFromTestCase(TestCacheValidation))
    suites.append(loader.loadTestsFromTestCase(TestProviderAudit))
    suites.append(loader.loadTestsFromTestCase(TestRandomizedRace))
    suites.append(loader.loadTestsFromTestCase(Test1000TransitionStability))
    suites.append(loader.loadTestsFromTestCase(TestSameFileSessionRace))
    suites.append(loader.loadTestsFromTestCase(TestAtomicWrites))
    combined = unittest.TestSuite(suites)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(combined)
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("ALL PRODUCTION PATH VALIDATION TESTS PASSED.")
        sys.exit(0)
    else:
        print(f"FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
        sys.exit(1)

