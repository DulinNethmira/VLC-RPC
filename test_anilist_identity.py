"""Focused regression tests for the AniList identity and sync safety boundary."""

import threading

import vlc_discord_rpc_gui as app


def make_backend():
    backend = app.RPCBackend.__new__(app.RPCBackend)
    backend.config = {"anilist_token": "test-token"}
    backend.state_data = {
        "metadata": {"genres": ["Drama"], "rating": 8.4, "image_url": "cover.jpg"},
        "episode_str": "Episode 1",
        "anilist_identity": None,
        "anilist_identity_state": "UNKNOWN",
    }
    backend.metadata_cache = {}
    backend.anilist_identity_cache = {}
    backend.current_anilist_identity = None
    backend._anilist_identity_resolving = set()
    backend._anilist_identity_lock = threading.Lock()
    backend._anilist_media_list_refreshing = set()
    backend._rewatch_start_lock = threading.Lock()
    backend.logs = []
    backend.anilist_log = backend.logs.append
    backend.save_metadata_cache = lambda: None
    backend.force_sync_widget = lambda: None
    backend.force_sync_widget_v2 = lambda: None
    backend.refresh_anilist_media_list = lambda *_: False
    return backend


def candidate(media_id, title, format_="TV", episodes=12):
    return {
        "id": media_id,
        "type": "ANIME",
        "format": format_,
        "episodes": episodes,
        "title": {"english": title, "romaji": title, "native": title},
        "synonyms": [],
    }


def test_reject_unrelated_title():
    backend = make_backend()
    score, _ = backend._anilist_candidate_score(
        "You and I Are Polar Opposites", "Episode 7", candidate(21, "One Piece", episodes=1100)
    )
    assert score < app.ANILIST_IDENTITY_CONFIDENCE


def test_season_protection():
    backend = make_backend()
    season_one, _ = backend._anilist_candidate_score(
        "Example Anime Season 2", "Season 2 Episode 1", candidate(100, "Example Anime Season 1")
    )
    season_two, _ = backend._anilist_candidate_score(
        "Example Anime Season 2", "Season 2 Episode 1", candidate(200, "Example Anime Season 2")
    )
    assert season_one < app.ANILIST_IDENTITY_CONFIDENCE
    assert season_two >= app.ANILIST_IDENTITY_CONFIDENCE


def test_numeric_sequel_is_safe_for_an_explicit_season():
    backend = make_backend()
    score, _ = backend._anilist_candidate_score(
        "Farming Life in Another World Season 2",
        "Episode 7",
        candidate(197824, "Farming Life in Another World 2"),
    )
    wrong_score, _ = backend._anilist_candidate_score(
        "Farming Life in Another World Season 2",
        "Episode 7",
        candidate(146850, "Farming Life in Another World"),
    )
    assert score >= app.ANILIST_IDENTITY_CONFIDENCE
    assert wrong_score < app.ANILIST_IDENTITY_CONFIDENCE


def test_resolver_selects_exact_identity_only():
    backend = make_backend()
    key, _, _ = backend._anilist_identity_key("You and I Are Polar Opposites", "Episode 7")
    backend.current_anilist_identity = {"source_key": key, "state": "RESOLVING"}
    original_post = app.requests.post

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "data": {
                    "Page": {
                        "media": [
                            candidate(21, "One Piece", episodes=1100),
                            candidate(300, "You and I Are Polar Opposites", episodes=12),
                        ]
                    }
                }
            }

    app.requests.post = lambda *args, **kwargs: Response()
    try:
        backend._resolve_anilist_identity(key, "You and I Are Polar Opposites", "Episode 7")
    finally:
        app.requests.post = original_post
    assert backend.current_anilist_identity["anilist_id"] == 300
    assert backend.current_anilist_identity["state"] == "SYNCABLE"


def test_cache_reuse_and_metadata_preservation():
    backend = make_backend()
    key, _, _ = backend._anilist_identity_key("One Piece", "Episode 1168")
    backend.anilist_identity_cache[key] = {
        "anilist_id": 21,
        "source_key": key,
        "identity_version": app.ANILIST_IDENTITY_VERSION,
        "confidence": 0.98,
        "validated": True,
        "state": "SYNCABLE",
        "episodes": 1122,
    }
    backend.ensure_anilist_identity("One Piece", "Episode 1168")
    assert backend.current_anilist_identity["anilist_id"] == 21
    assert backend.state_data["metadata"]["genres"] == ["Drama"]
    assert backend.state_data["metadata"]["rating"] == 8.4
    assert backend.state_data["metadata"]["image_url"] == "cover.jpg"
    assert backend.state_data["metadata"]["anilistId"] == 21


def test_exact_legacy_metadata_is_upgraded_lazily():
    backend = make_backend()
    backend.metadata_cache = {
        "anime:Example Anime:Episode 1": {
            "anilistId": 500,
            "official_title": "Example Anime",
            "genres": ["Action"],
            "rating": 9.0,
            "image_url": "example.jpg",
            "total_episodes": 12,
        }
    }
    backend.ensure_anilist_identity("Example Anime", "Episode 1")
    assert backend.current_anilist_identity["anilist_id"] == 500
    assert backend.current_anilist_identity["validated"]
    assert backend.state_data["metadata"]["genres"] == ["Drama"]


def test_cross_anime_identity_cannot_sync():
    backend = make_backend()
    key_a, _, _ = backend._anilist_identity_key("Anime A", "Episode 13")
    backend.current_anilist_identity = {
        "anilist_id": 100,
        "source_key": key_a,
        "state": "SYNCABLE",
        "validated": True,
        "episodes": 24,
    }
    backend.state_data["episode_str"] = "Episode 1"
    success, _ = backend.sync_anilist("Anime B", 1)
    assert not success
    assert any("not verified" in entry for entry in backend.logs)


def test_sync_uses_verified_id_without_search():
    backend = make_backend()
    key, _, _ = backend._anilist_identity_key("Anime B", "Episode 1")
    backend.current_anilist_identity = {
        "anilist_id": 200,
        "source_key": key,
        "state": "SYNCABLE",
        "validated": True,
        "episodes": 12,
    }
    calls = []
    original_post = app.requests.post

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"data": {"SaveMediaListEntry": {"id": 1, "progress": 1, "status": "CURRENT"}}}

    def post(url, json, headers, timeout):
        calls.append(json)
        return Response()

    app.requests.post = post
    try:
        success, status = backend.sync_anilist("Anime B", 1)
    finally:
        app.requests.post = original_post
    assert success and status == "CURRENT"
    assert calls[0]["variables"]["mediaId"] == 200
    assert "search" not in calls[0]["query"].lower()
    assert "$repeat" not in calls[0]["query"]


def test_explicit_rewatch_uses_same_media_id_once():
    backend = make_backend()
    key, _, _ = backend._anilist_identity_key("Anime B", "Episode 1")
    identity = {
        "anilist_id": 200,
        "source_key": key,
        "state": "SYNCABLE",
        "validated": True,
        "episodes": 12,
    }
    backend.current_anilist_identity = identity
    backend.state_data["anilist_identity"] = identity.copy()
    calls = []
    original_post = app.requests.post

    class Response:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    def post(url, json, headers, timeout):
        calls.append(json)
        if "MediaList(" in json["query"]:
            return Response({"data": {"MediaList": {
                "id": 1, "status": "COMPLETED", "progress": 12, "repeat": 1,
                "media": {"id": 200, "episodes": 12},
            }}})
        return Response({"data": {"SaveMediaListEntry": {
            "id": 1, "status": "REPEATING", "progress": 0, "repeat": 2,
            "media": {"id": 200, "episodes": 12},
        }}})

    app.requests.post = post
    try:
        assert backend._start_anilist_rewatch()
    finally:
        app.requests.post = original_post
    mutation = calls[-1]
    assert mutation["variables"] == {
        "mediaId": 200, "progress": 0, "status": "REPEATING", "repeat": 2,
    }
    assert backend.state_data["watch_mode"] == "REWATCH"
    assert backend.state_data["rewatch_number"] == 2


if __name__ == "__main__":
    test_reject_unrelated_title()
    test_season_protection()
    test_numeric_sequel_is_safe_for_an_explicit_season()
    test_resolver_selects_exact_identity_only()
    test_cache_reuse_and_metadata_preservation()
    test_exact_legacy_metadata_is_upgraded_lazily()
    test_cross_anime_identity_cannot_sync()
    test_sync_uses_verified_id_without_search()
    test_explicit_rewatch_uses_same_media_id_once()
    print("AniList identity tests passed")
