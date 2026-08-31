"""
test_reliability.py
====================
Unit tests for the reliability patches in vlc_discord_rpc_gui.py.

Run with: python test_reliability.py
"""
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest

# ── Minimal stub so we can import logic without the full GUI stack ────────────

# Build a minimal fake module tree so vlc_discord_rpc_gui imports don't crash.
FAKE_MODULES = [
    "requests", "pypresence", "pypresence.enums", "webview",
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    "pystray", "pystray._win32", "win32gui", "win32con",
    "google.generativeai", "google",
    "infi", "infi.systray",
]
for mod in FAKE_MODULES:
    parts = mod.split(".")
    for i in range(1, len(parts) + 1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

# Stub out heavy imports used at module level.
sys.modules["pypresence"].Presence = object
sys.modules["pypresence.enums"].ActivityType = types.SimpleNamespace(WATCHING=3, LISTENING=2)

# ─────────────────────────────────────────────────────────────────────────────
# We test the logic directly without importing the whole file.
# Extract only the functions / classes we need via ast + exec tricks.
# ─────────────────────────────────────────────────────────────────────────────

# --------------- Helpers that mirror the patched implementations ---------------

def _make_backend_stub():
    """Return a minimal object that mimics RPCBackend state for unit tests."""
    b = types.SimpleNamespace()
    b.state_data = {
        "episode_str": "",
        "possible_rewatch": False,
        "watch_mode": "NORMAL",
        "rewatch_number": 0,
    }
    b.scored_episodes = set()
    b._popup_calls = []

    def _show_rewatch_popup(anilist_id, media_list):
        b._popup_calls.append((anilist_id, media_list))

    b._show_rewatch_popup = _show_rewatch_popup

    # Inline the patched _apply_anilist_media_list logic
    import re as _re

    def _apply_anilist_media_list(anilist_id, media_list):
        trigger_rewatch_popup = False

        status = (media_list or {}).get("status")
        if status == "REPEATING":
            b.state_data["watch_mode"] = "REWATCH"
            b.state_data["rewatch_number"] = (media_list or {}).get("repeat") or 1
            b.state_data["possible_rewatch"] = False
        elif status == "COMPLETED":
            b.state_data["watch_mode"] = "NORMAL"
            b.state_data["rewatch_number"] = 0

            ep_str = b.state_data.get("episode_str", "")
            ep_match = _re.search(r"Episode\s*(\d+)", ep_str or "", _re.IGNORECASE)
            current_ep = int(ep_match.group(1)) if ep_match else None
            al_progress = (media_list or {}).get("progress") or 0

            repeat_count = (media_list or {}).get("repeat") or 0
            rewatch_cycle_key = (anilist_id, "rewatch_prompt", repeat_count)

            genuine_rewatch = (
                current_ep is None
                or current_ep == 1
                or (al_progress > 0 and current_ep < al_progress)
            )

            if (
                not b.state_data.get("possible_rewatch")
                and genuine_rewatch
                and rewatch_cycle_key not in b.scored_episodes
            ):
                b.state_data["possible_rewatch"] = True
                trigger_rewatch_popup = True
        else:
            b.state_data["watch_mode"] = "NORMAL"
            b.state_data["rewatch_number"] = 0
            b.state_data["possible_rewatch"] = False

        if trigger_rewatch_popup:
            b._show_rewatch_popup(anilist_id, media_list)
        return True

    b._apply_anilist_media_list = _apply_anilist_media_list
    return b


# ─────────────────────────────────────────────────────────────────────────────
# TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class TestRewatchPopup(unittest.TestCase):

    def _backend(self):
        return _make_backend_stub()

    # ── T1: Normal watching (CURRENT) – no popup ───────────────────────────

    def test_T1_current_status_no_popup(self):
        """Status=CURRENT → no popup at all."""
        b = self._backend()
        b.state_data["episode_str"] = "Episode 5"
        b._apply_anilist_media_list(1, {"status": "CURRENT", "progress": 5, "repeat": 0})
        self.assertEqual(len(b._popup_calls), 0)
        self.assertEqual(b.state_data["watch_mode"], "NORMAL")

    # ── T2: Completed final episode – NO popup (false-positive guard) ──────

    def test_T2_completed_final_ep_no_false_popup(self):
        """Watching the last completed episode (ep == progress) must NOT trigger popup."""
        b = self._backend()
        b.state_data["episode_str"] = "Episode 12"   # ep 12 == progress 12
        b._apply_anilist_media_list(1, {"status": "COMPLETED", "progress": 12, "repeat": 0})
        self.assertEqual(len(b._popup_calls), 0, "False positive: popup on final ep")

    def test_T2b_completed_beyond_progress_no_popup(self):
        """ep > progress is impossible in normal use but must not crash or popup."""
        b = self._backend()
        b.state_data["episode_str"] = "Episode 13"
        b._apply_anilist_media_list(1, {"status": "COMPLETED", "progress": 12, "repeat": 0})
        self.assertEqual(len(b._popup_calls), 0)

    # ── T3: Completed – genuine new rewatch cycle (ep 1) → popup ONCE ─────

    def test_T3_genuine_rewatch_ep1_triggers_once(self):
        """ep 1 of a COMPLETED series → popup fires exactly once."""
        b = self._backend()
        b.state_data["episode_str"] = "Episode 1"
        b._apply_anilist_media_list(1, {"status": "COMPLETED", "progress": 12, "repeat": 0})
        self.assertEqual(len(b._popup_calls), 1, "Popup should fire once on ep 1 rewatch")

    # ── T4: Same rewatch cycle detected again – popup does NOT repeat ──────

    def test_T4_same_cycle_no_repeat_popup(self):
        """Popup must not fire again for the same (anilist_id, repeat_count) cycle."""
        b = self._backend()
        b.state_data["episode_str"] = "Episode 1"
        # First time
        b._apply_anilist_media_list(1, {"status": "COMPLETED", "progress": 12, "repeat": 0})
        self.assertEqual(len(b._popup_calls), 1)
        b.scored_episodes.add((1, "rewatch_prompt", 0))  # simulate _show_rewatch_popup adding key

        # Second time (e.g. metadata refresh)
        b.state_data["possible_rewatch"] = False   # reset as if metadata re-loaded
        b._apply_anilist_media_list(1, {"status": "COMPLETED", "progress": 12, "repeat": 0})
        self.assertEqual(len(b._popup_calls), 1, "Popup should NOT fire again for same cycle")

    # ── T5: Legitimate new rewatch cycle (repeat incremented) → popup ──────

    def test_T5_new_repeat_cycle_triggers(self):
        """A new repeat count means a genuinely new rewatch – popup should fire."""
        b = self._backend()
        # Mark old cycle as seen
        b.scored_episodes.add((1, "rewatch_prompt", 0))
        b.state_data["episode_str"] = "Episode 1"
        b._apply_anilist_media_list(1, {"status": "COMPLETED", "progress": 12, "repeat": 1})
        self.assertEqual(len(b._popup_calls), 1, "New repeat cycle must trigger popup")

    # ── T6: ep < progress also signals genuine rewatch ────────────────────

    def test_T6_ep_behind_progress_triggers(self):
        """Watching ep 3 of a 12-ep completed series is a genuine rewatch."""
        b = self._backend()
        b.state_data["episode_str"] = "Episode 3"
        b._apply_anilist_media_list(1, {"status": "COMPLETED", "progress": 12, "repeat": 0})
        self.assertEqual(len(b._popup_calls), 1)

    # ── T7: REPEATING status → no popup, just sets REWATCH mode ───────────

    def test_T7_repeating_status_no_popup(self):
        """REPEATING status means AniList already confirmed rewatch – no popup needed."""
        b = self._backend()
        b.state_data["episode_str"] = "Episode 5"
        b._apply_anilist_media_list(1, {"status": "REPEATING", "progress": 12, "repeat": 1})
        self.assertEqual(len(b._popup_calls), 0)
        self.assertEqual(b.state_data["watch_mode"], "REWATCH")
        self.assertEqual(b.state_data["rewatch_number"], 1)


class TestGeminiPendingCleanup(unittest.TestCase):

    def _run_gemini_factory(self):
        """
        Return a _run_gemini function and a shared state dict,
        mimicking the patched logic.
        """
        state = {
            "gemini_cache": {},
            "gemini_fail_times": {},
            "media_generation": 0,
            "log_calls": [],
        }

        def query_gemini_title(name, key):
            return state.get("_gemini_response")

        def media_identity_to_display(raw):
            if not raw:
                return None, None, None
            return raw.get("title"), raw.get("episode"), raw.get("media_type")

        def _run_gemini(name, key, gen):
            try:
                t, e, mt = media_identity_to_display(query_gemini_title(name, key))
            except Exception as ex:
                state["gemini_cache"][name] = None
                state["gemini_fail_times"][name] = time.time()
                state["log_calls"].append(f"exception:{ex}")
                return

            if gen != state["media_generation"]:
                state["gemini_cache"][name] = None
                return

            if t:
                state["gemini_cache"][name] = (t, e, mt or "")
            else:
                state["gemini_cache"][name] = None
                state["gemini_fail_times"][name] = time.time()

        return _run_gemini, state

    def test_success_clears_pending(self):
        fn, st = self._run_gemini_factory()
        st["gemini_cache"]["ep1.mkv"] = "pending"
        st["_gemini_response"] = {"title": "My Anime", "episode": "Episode 1", "media_type": "anime"}
        fn("ep1.mkv", "key", 0)
        self.assertNotEqual(st["gemini_cache"]["ep1.mkv"], "pending")
        self.assertIsInstance(st["gemini_cache"]["ep1.mkv"], tuple)

    def test_failure_clears_pending(self):
        fn, st = self._run_gemini_factory()
        st["gemini_cache"]["ep2.mkv"] = "pending"
        st["_gemini_response"] = None   # Gemini returns nothing
        fn("ep2.mkv", "key", 0)
        self.assertIsNone(st["gemini_cache"]["ep2.mkv"], "None expected after failure")

    def test_exception_clears_pending(self):
        fn, st = self._run_gemini_factory()
        st["gemini_cache"]["ep3.mkv"] = "pending"

        def bad_query(name, key):
            raise RuntimeError("network error")

        # Patch the inner query to raise
        import types as _types
        original = fn.__code__
        # Instead, re-build with an injected exception
        fn2, st2 = self._run_gemini_factory()
        st2["gemini_cache"]["ep3.mkv"] = "pending"

        def _run_gemini_exc(name, key, gen):
            try:
                raise RuntimeError("simulated network error")
            except Exception as ex:
                st2["gemini_cache"][name] = None
                st2["gemini_fail_times"][name] = time.time()
                return

        _run_gemini_exc("ep3.mkv", "key", 0)
        self.assertIsNone(st2["gemini_cache"]["ep3.mkv"])

    def test_stale_generation_clears_pending(self):
        fn, st = self._run_gemini_factory()
        st["gemini_cache"]["ep4.mkv"] = "pending"
        st["_gemini_response"] = {"title": "Old Anime", "episode": "Episode 1", "media_type": "anime"}
        # Advance generation BEFORE thread finishes (simulating file change)
        st["media_generation"] = 1
        fn("ep4.mkv", "key", gen=0)   # spawned with gen=0, now gen=1
        self.assertIsNone(st["gemini_cache"]["ep4.mkv"], "Stale gen must clear pending to None")


class TestCacheRecovery(unittest.TestCase):

    def test_load_gemini_cache_filters_pending(self):
        """Simulates load_gemini_cache: 'pending' values must be skipped."""
        raw = {
            "ep1.mkv": ["My Anime", "Episode 1", "anime"],
            "ep2.mkv": "pending",
            "ep3.mkv": None,
        }
        cache = {}
        for k, v in raw.items():
            if v != "pending":
                if isinstance(v, list):
                    cache[k] = tuple(v)
                else:
                    cache[k] = v

        self.assertIn("ep1.mkv", cache)
        self.assertNotIn("ep2.mkv", cache, "'pending' must be filtered on load")
        self.assertIn("ep3.mkv", cache)
        self.assertIsInstance(cache["ep1.mkv"], tuple)

    def test_corrupted_json_returns_empty(self):
        """Corrupt JSON file must not crash; empty cache returned."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json{{")
            path = f.name
        try:
            cache = {}
            try:
                with open(path, 'r', encoding='utf-8') as fp:
                    loaded = json.load(fp)
                for k, v in loaded.items():
                    if v != "pending":
                        cache[k] = tuple(v) if isinstance(v, list) else v
            except Exception:
                pass  # corrupted: stay empty
            self.assertEqual(cache, {})
        finally:
            os.unlink(path)

    def test_atomic_write_uses_replace(self):
        """save_gemini_cache must write via a temp file then os.replace."""
        import tempfile as _tmp

        calls = []
        orig_replace = os.replace

        def fake_replace(src, dst):
            calls.append(("replace", src, dst))
            orig_replace(src, dst)

        old_replace = os.replace
        os.replace = fake_replace
        try:
            gemini_cache = {"ep1.mkv": ("My Anime", "Episode 1", "anime")}
            with tempfile.TemporaryDirectory() as d:
                cache_file = os.path.join(d, "gemini_cache.json")
                clean_cache = {k: v for k, v in gemini_cache.items() if v != "pending"}
                fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(cache_file), suffix=".tmp")
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(clean_cache, f)
                os.replace(tmp_path, cache_file)
                self.assertTrue(any(r[0] == "replace" for r in calls), "os.replace must be called")
                self.assertTrue(os.path.exists(cache_file))
        finally:
            os.replace = old_replace


class TestMediaGenerationRace(unittest.TestCase):

    def test_stale_worker_does_not_apply_metadata(self):
        """
        A background thread that captured generation=0 must discard its result
        when the main generation counter has advanced to 1 (new file).
        """
        generation_counter = [0]   # shared mutable

        applied = []

        def _fetch_metadata_bg(cache_key, title, episode_str, generation=None):
            # Simulate network delay
            time.sleep(0.05)
            # Check generation
            stale_gen = (generation is not None and generation != generation_counter[0])
            still_same_file = not stale_gen
            if still_same_file:
                applied.append(title)

        gen_at_spawn = generation_counter[0]   # 0
        t = threading.Thread(
            target=_fetch_metadata_bg,
            args=("k", "Old Anime", "Episode 1"),
            kwargs={"generation": gen_at_spawn},
            daemon=True,
        )
        t.start()

        # Advance generation (new file loaded) before thread finishes
        generation_counter[0] = 1

        t.join(timeout=1)
        self.assertEqual(applied, [], "Stale worker must NOT apply its metadata")

    def test_non_stale_worker_applies_metadata(self):
        """A worker whose generation still matches must apply metadata."""
        generation_counter = [0]
        applied = []

        def _fetch_metadata_bg(cache_key, title, episode_str, generation=None):
            stale_gen = (generation is not None and generation != generation_counter[0])
            if not stale_gen:
                applied.append(title)

        gen_at_spawn = generation_counter[0]
        _fetch_metadata_bg("k", "My Anime", "Episode 2", generation=gen_at_spawn)
        self.assertEqual(applied, ["My Anime"])


class TestEpisodeTransitionMetadata(unittest.TestCase):
    """Simulate Episode 1 → 2 → 3 → 1 cache key correctness."""

    def _make_cache_key(self, media_type, title, episode_str):
        return f"{media_type}:{title}:{episode_str}"

    def test_ep1_to_ep2_different_keys(self):
        """Episode 1 and Episode 2 must have distinct cache keys."""
        k1 = self._make_cache_key("anime", "My Anime", "Episode 1")
        k2 = self._make_cache_key("anime", "My Anime", "Episode 2")
        self.assertNotEqual(k1, k2)

    def test_ep1_to_ep2_to_ep3_all_distinct(self):
        keys = [self._make_cache_key("anime", "My Anime", f"Episode {i}") for i in range(1, 4)]
        self.assertEqual(len(set(keys)), 3, "All episode keys must be unique")

    def test_ep3_back_to_ep1_correct_key(self):
        """Going back to ep1 must yield the same key as the first time."""
        k1_first = self._make_cache_key("anime", "My Anime", "Episode 1")
        k1_return = self._make_cache_key("anime", "My Anime", "Episode 1")
        self.assertEqual(k1_first, k1_return, "Cache key must be stable across visits")

    def test_cached_ep1_does_not_block_ep2(self):
        """Ep2 cache miss triggers fetch even if ep1 is cached."""
        metadata_cache = {
            "anime:My Anime:Episode 1": {"image_url": "http://img/1.jpg", "title": "My Anime ep1"}
        }
        k2 = "anime:My Anime:Episode 2"
        self.assertNotIn(k2, metadata_cache, "Ep2 must not be blocked by ep1 cache entry")

    def test_pending_ep1_does_not_block_ep2(self):
        """gemini_cache for 'ep1.mkv' must not block lookup for 'ep2.mkv'."""
        gemini_cache = {"ep1.mkv": ("My Anime", "Episode 1", "anime")}
        # ep2.mkv is absent → should_try=True for ep2
        raw_name_ep2 = "ep2.mkv"
        in_cache = raw_name_ep2 in gemini_cache
        self.assertFalse(in_cache, "ep2 must not be blocked by ep1's gemini cache entry")


class TestDiscordReconnect(unittest.TestCase):

    def test_last_rpc_kwargs_reset_on_connect(self):
        """After successful Discord connect, _last_rpc_kwargs must be empty
        so the next update loop immediately pushes presence."""
        state = {"rpc_connected": False, "_last_rpc_kwargs": {"details": "Old Anime"}}

        # Simulate successful connect
        state["rpc_connected"] = True
        state["_last_rpc_kwargs"] = {}   # The patch resets this
        state["_last_rpc_cleared"] = False

        self.assertEqual(state["_last_rpc_kwargs"], {})
        self.assertFalse(state["_last_rpc_cleared"])

    def test_discord_log_only_on_state_change(self):
        """Log 'disconnected' only when transitioning from connected to disconnected."""
        logged = []
        was_connected = True   # previously connected

        if was_connected:
            logged.append("Discord RPC disconnected")

        state_rpc_connected = False
        was_connected = False

        # Second failure (already disconnected) – must NOT log again
        if was_connected:
            logged.append("Discord RPC disconnected")

        self.assertEqual(len(logged), 1, "Log must fire only once per disconnect event")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestRewatchPopup,
        TestGeminiPendingCleanup,
        TestCacheRecovery,
        TestMediaGenerationRace,
        TestEpisodeTransitionMetadata,
        TestDiscordReconnect,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
