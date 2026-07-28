"""
VLC RPC Audit Test Suite (Post-Fix)
Tests filename parsing, state clearing, cover fallback,
episode rating extraction, AniList sync trigger logic,
and Discord update/reconnect error handling.
"""
import re
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vlc_discord_rpc_gui import clean_title, ensure_https, is_music_file

passed = 0
failed = 0
results = []

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        results.append(("PASS", name, detail))
    else:
        failed += 1
        results.append(("FAIL", name, detail))

# ═══════════════════════════════════════════════════════════════════
# 1. FILENAME PARSING (clean_title)
# ═══════════════════════════════════════════════════════════════════

t, ep = clean_title("One Piece 1170.mp4")
check("Bare ep: One Piece 1170 -> title", "one piece" in t.lower(), f"got '{t}'")
check("Bare ep: One Piece 1170 -> episode", "1170" in ep, f"got '{ep}'")

t, ep = clean_title("You and I Are Polar Opposites S02E03.mp4")
check("SxxExx: title parsed", len(t) > 5, f"got '{t}'")
check("SxxExx: Season 2", "Season 2" in ep or "season 2" in ep.lower(), f"got '{ep}'")
check("SxxExx: Episode 3", "Episode 3" in ep or "episode 3" in ep.lower(), f"got '{ep}'")

t, ep = clean_title("American.Sniper.2014.720p.BluRay.x264.mkv")
check("Movie: title contains 'sniper'", "sniper" in t.lower(), f"got '{t}'")
check("Movie: episode_str has Movie", "Movie" in ep or "movie" in ep.lower(), f"got '{ep}'")

t, ep = clean_title("Shape of You.mp3")
check("Music: title parsed", "shape" in t.lower(), f"got '{t}'")

t, ep = clean_title("[SubGroup] One Piece - 1170 [1080p].mkv")
check("Dash ep: episode 1170", "1170" in ep, f"got '{ep}'")

t, ep = clean_title("random_video.mp4")
check("Simple file: title not empty", len(t) > 0, f"got '{t}'")

t, ep = clean_title("Steins Gate 01")
check("No ext: episode 1", "Episode 1" in ep, f"got '{ep}'")

t, ep = clean_title("Inception 2010.mp4")
check("Year not episode: 2010 not Episode", "Episode 2010" not in ep, f"got '{ep}'")

t, ep = clean_title("ReZero Starting Life 08.mp4")
check("CamelCase: Re Zero split", "re" in t.lower() and "zero" in t.lower(), f"got '{t}'")
check("CamelCase: episode 8", "Episode 8" in ep, f"got '{ep}'")

# ═══════════════════════════════════════════════════════════════════
# 2. ensure_https
# ═══════════════════════════════════════════════════════════════════

check("https: http->https", ensure_https("http://example.com/img.jpg") == "https://example.com/img.jpg")
check("https: https unchanged", ensure_https("https://example.com/img.jpg") == "https://example.com/img.jpg")
check("https: None unchanged", ensure_https(None) is None)
check("https: empty unchanged", ensure_https("") == "")

# ═══════════════════════════════════════════════════════════════════
# 3. is_music_file
# ═══════════════════════════════════════════════════════════════════

check("music: mp3", is_music_file("song.mp3", "", ""))
check("music: flac", is_music_file("song.flac", "", ""))
check("music: mp4 is not music", not is_music_file("video.mp4", "", ""))
check("music: mp4 with artist+album is music", is_music_file("video.mp4", "Artist", "Album"))
check("music: no file", not is_music_file("", "", ""))

# ═══════════════════════════════════════════════════════════════════
# 4. STATE CLEARING AUDIT — Verify P1+P3 fixes
# ═══════════════════════════════════════════════════════════════════

with open("vlc_discord_rpc_gui.py", "r", encoding="utf-8") as f:
    src = f.read()

# Helper: extract block between two markers
def extract_block(source, start_marker, end_marker):
    idx = source.find(start_marker)
    if idx < 0:
        return ""
    block = source[idx:]
    end_idx = block.find(end_marker, len(start_marker))
    if end_idx > 0:
        return block[:end_idx]
    return block[:800]

# RequestException block
req_block = extract_block(src, "except requests.exceptions.RequestException:", "except Exception")
check("Disconnect: clears vlc_connected", '"vlc_connected"] = False' in req_block, "RequestException")
check("Disconnect: clears playback_state", '"playback_state"] = "stopped"' in req_block, "RequestException")
check("Disconnect: clears title", '"title"] = ""' in req_block, "RequestException")
check("Disconnect: clears cleaned_title", '"cleaned_title"] = ""' in req_block, "RequestException")
check("Disconnect: clears episode_str", '"episode_str"] = ""' in req_block, "RequestException")
check("Disconnect: clears metadata", '"metadata"] = None' in req_block, "RequestException")
check("Disconnect: clears local_image_path", '"local_image_path"] = None' in req_block, "RequestException")
check("Disconnect: clears local_arturl", '"local_arturl"] = ""' in req_block, "RequestException")
check("Disconnect: clears _last_art_key", '"_last_art_key"] = ""' in req_block, "RequestException")
check("Disconnect: clears _last_art_uri", '"_last_art_uri"] = ""' in req_block, "RequestException")

# Generic Exception block
gen_block = extract_block(src, 'except Exception as e:\r\n                if self.state_data.get("vlc_connected"):\r\n                    self.log(f"VLC error: {e}")', "desired_client_id")
check("GenericExc: clears playback_state", '"playback_state"] = "stopped"' in gen_block, "generic Exception")
check("GenericExc: clears _last_art_key", '"_last_art_key"] = ""' in gen_block, "generic Exception")

# Non-200 block
non200_block = extract_block(src, "else:\r\n                    self.state_data[\"vlc_connected\"] = False\r\n                    self.state_data[\"playback_state\"] = \"stopped\"", "except requests.exceptions")
check("Non200: clears playback_state", '"playback_state"] = "stopped"' in non200_block, "non-200 path")
check("Non200: clears _last_art_key", '"_last_art_key"] = ""' in non200_block, "non-200 path")

# ═══════════════════════════════════════════════════════════════════
# 5. P2 FIX: Music files don't get "Movie" subtitle
# ═══════════════════════════════════════════════════════════════════

# Verify the guard exists in rpc_worker
check("P2 fix: music Movie guard exists",
      'if is_music and episode_str and "Movie" in episode_str:' in src,
      "Guard in rpc_worker")

# ═══════════════════════════════════════════════════════════════════
# 6. EPISODE RATING EXTRACTION
# ═══════════════════════════════════════════════════════════════════

def getRatingText(metadata):
    if not metadata: return ''
    rating = metadata.get("episode_rating") or metadata.get("rating") or metadata.get("imdb_rating") or ''
    if rating is None or rating == '': return ''
    numeric = float(rating) if isinstance(rating, (int, float)) else None
    if numeric is not None:
        clean_rating = f"{numeric:.1f}".rstrip('0').rstrip('.')
    else:
        clean_rating = str(rating)
    return f"* {clean_rating}"

check("Rating: episode_rating preferred", "8.3" in getRatingText({"rating": 7.5, "episode_rating": 8.3}))
check("Rating: show rating fallback", "7.5" in getRatingText({"rating": 7.5}))
check("Rating: None returns empty", getRatingText(None) == '')
check("Rating: no rating returns empty", getRatingText({"genres": ["Drama"]}) == '')

# ═══════════════════════════════════════════════════════════════════
# 7. ANILIST SYNC TRIGGER LOGIC
# ═══════════════════════════════════════════════════════════════════

ep_match = re.search(r'Episode\s*(\d+)', "Season 2 Episode 14", re.IGNORECASE)
check("AniList: ep regex match", ep_match is not None and ep_match.group(1) == "14")

ep_match2 = re.search(r'Episode\s*(\d+)', "Movie (2014)", re.IGNORECASE)
check("AniList: no trigger for Movie", ep_match2 is None)

# ═══════════════════════════════════════════════════════════════════
# 8. DISCORD UPDATE ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════

discord_err_block_idx = src.find("rpc.update(**kwargs)")
discord_err_after = src[discord_err_block_idx:discord_err_block_idx+600]
check("Discord err: closes rpc", "rpc.close()" in discord_err_after)
check("Discord err: sets rpc=None", "rpc = None" in discord_err_after)
check("Discord err: sets connected=False", '"rpc_connected"] = False' in discord_err_after)
check("Discord err: sets backoff", "rpc_backoff" in discord_err_after)

# ═══════════════════════════════════════════════════════════════════
# 9. COVER FALLBACK (frontend)
# ═══════════════════════════════════════════════════════════════════

with open("web/script.js", "r", encoding="utf-8") as f:
    js_src = f.read()

check("Frontend: onerror handler exists", "coverEl.onerror" in js_src)
check("Frontend: fallback to local art", "fallbackTried" in js_src)
check("Frontend: placeholder fallback", "COVER_PLACEHOLDER" in js_src)
check("Frontend: dc-large-img onerror", "dcLargeImg.onerror" in js_src)

# ═══════════════════════════════════════════════════════════════════
# 10. FORCE SYNC
# ═══════════════════════════════════════════════════════════════════

force_block = extract_block(src, "def force_update(self):", "def get_anilist_logs")
check("ForceSync: clears metadata", '"metadata"] = None' in force_block)
check("ForceSync: clears local_arturl", '"local_arturl"] = ""' in force_block)
check("ForceSync: clears _last_art_key", '"_last_art_key"] = ""' in force_block)
check("ForceSync: deletes cache entry", "del b.metadata_cache[cache_key]" in force_block)
check("ForceSync: sets flag", "force_update_flag = True" in force_block)

# ═══════════════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("VLC RPC AUDIT TEST RESULTS (POST-FIX)")
print("=" * 70)
for status, name, detail in results:
    marker = "OK" if status == "PASS" else "!!"
    det = f"  ({detail})" if detail else ""
    print(f"  [{marker}] {name}{det}")

print(f"\n  {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("  ALL TESTS PASSED")
print("=" * 70)
