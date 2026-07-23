import os
import sys
import time
import json
import threading
import re
import urllib.parse
import hashlib
import requests
from requests.auth import HTTPBasicAuth
import asyncio
from io import BytesIO
import sqlite3
import datetime
import winreg
try:
    import guessit
except ImportError:
    guessit = None
from pypresence import Presence, ActivityType
import webview
import pystray
from PIL import Image

CONFIG_FILE = "config.json"
CACHE_FILE = "metadata_cache.json"
COVERS_DIR = "covers_cache"
DEFAULT_CLIENT_ID = "1465711556418474148"
CURRENT_VERSION = "3.6"
GITHUB_REPO = "DulinNethmira/VLC-RPC"

DEFAULT_CONFIG = {
    "client_id": DEFAULT_CLIENT_ID,
    "vlc_host": "localhost",
    "vlc_port": 8080,
    "vlc_password": "",
    "update_interval": 2,
    "large_image_key": "vlc",
    "large_image_text": "VLC Media Player",
    "small_image_key": "play",
    "small_image_text": "Playing",
    "small_image_paused_key": "pause",
    "small_image_paused_text": "Paused",
    "gemini_api_key": ""
}

def query_gemini_title(filename, api_key):
    """Use Gemini REST API to extract official anime title and episode."""
    if not api_key: return None, None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = f"You are an anime metadata extractor. Extract the official English or Romaji anime title and episode number from this video filename. Do not include seasons in the title if it's not part of the official name. Return strictly JSON: {{\"title\": \"<title>\", \"episode\": <number_or_null>}}. Filename: {filename}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code == 200:
            data = r.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            parsed = json.loads(text)
            title = parsed.get("title")
            ep = parsed.get("episode")
            ep_str = f"Episode {ep}" if ep else ""
            return title, ep_str
    except Exception as e:
        print(f"Gemini AI Error: {e}")
    return None, None

def clean_title(title):
    """Parse a raw filename into (display_title, episode_str).
    Works for both anime/TV  (S01E04, Episode 4) and movies
    (American.Sniper.2014.720p.BluRay…)."""
    title = str(title or "")
    title = re.sub(r'\.(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', title, flags=re.I).strip()
    title = re.sub(r'\s+(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', title, flags=re.I).strip()
    
    # Un-camelcase words for messy filenames (e.g., "ReZero" -> "Re Zero")
    title = re.sub(r'([a-z])([A-Z])', r'\1 \2', title)

    loose_ep = re.search(r"(?<!\d)([A-Za-z][\w\s\.'\-:&!,]+?)[\s\.\-_]+(?:Episode|Ep|E)?\s*(\d{1,4})(?:v\d+)?\s*$", title, re.I)
    if loose_ep:
        ep_num = int(loose_ep.group(2))
        explicit_ep = re.search(r'\b(?:Episode|Ep|E)\s*\d{1,4}\s*$', title, re.I)
        if explicit_ep or not (1900 <= ep_num <= 2099):
            cleaned = re.sub(r'[\s\.\-_]+', ' ', loose_ep.group(1)).strip()
            return ' '.join(w.capitalize() for w in cleaned.split()), f"Episode {ep_num}"

    if guessit:
        try:
            guessed = guessit.guessit(title)
            cleaned = guessed.get('title', title)
            episode_str = ""
            media_type = guessed.get('type', '')

            if media_type == 'movie':
                year = guessed.get('year')
                if year:
                    cleaned = f"{cleaned} ({year})"
                    episode_str = f"Movie ({year})"
                else:
                    episode_str = "Movie"
            elif media_type == 'episode':
                season = guessed.get('season')
                episode = guessed.get('episode')
                if season and episode:
                    if isinstance(season, list): season = season[0]
                    if isinstance(episode, list): episode = episode[0]
                    episode_str = f"Season {season} Episode {episode}"
                elif episode:
                    if isinstance(episode, list): episode = episode[0]
                    episode_str = f"Episode {episode}"

            # Title-case while preserving uppercase acronyms (e.g. "YIFY"->"Yify" is fine)
            if cleaned and isinstance(cleaned, str):
                cleaned = ' '.join(w.capitalize() for w in str(cleaned).split())

            return str(cleaned), episode_str
        except Exception:
            pass

    # --- Regex fallback ---
    title = re.sub(r'\[[^\]]*\]', '', title)
    title = re.sub(r'\([^\)]*\)', '', title)

    episode_str = ""
    # TV season/episode
    se_match = re.search(r'\bS(\d+)\s*E(\d+)\b', title, re.IGNORECASE)
    if se_match:
        episode_str = f"Season {int(se_match.group(1))} Episode {int(se_match.group(2))}"
        title = re.sub(r'\bS\d+\s*E\d+\b', '', title, flags=re.IGNORECASE)
    elif re.search(r'\b(?:Episode|Ep)\s*(\d+)\b', title, re.IGNORECASE):
        ep_match = re.search(r'\b(?:Episode|Ep)\s*(\d+)\b', title, re.IGNORECASE)
        episode_str = f"Episode {int(ep_match.group(1))}"
        title = re.sub(r'\b(?:Episode|Ep)\s*\d+\b', '', title, flags=re.IGNORECASE)
    elif re.search(r'-\s*(\d+)\b', title):
        dash_match = re.search(r'-\s*(\d+)\b', title)
        episode_str = f"Episode {int(dash_match.group(1))}"
        title = re.sub(r'-\s*\d+\b', '', title)

    # Movie year detection (regex fallback)
    year_match = re.search(r'\b(19|20)\d{2}\b', title)
    if year_match and not episode_str:
        episode_str = f"Movie ({year_match.group()})"

    words_to_remove = [
        r'\b1080p\b', r'\b720p\b', r'\b480p\b', r'\b2160p\b', r'\b4k\b',
        r'\bbluray\b', r'\bwebrip\b', r'\bweb-dl\b', r'\bdvdrip\b',
        r'\bx264\b', r'\bx265\b', r'\bh264\b', r'\bhevc\b',
        r'\bdual[- ]audio\b', r'\bmulti\b', r'\beng\b', r'\bsub\b', r'\bdub\b',
        r'\byify\b', r'\bxvid\b', r'\baac\b', r'\byts\b', r'\b\[yts\.mx\]\b',
        r'\brepack\b', r'\bextended\b'

    ]

    for word in words_to_remove:

        title = re.sub(word, '', title, flags=re.IGNORECASE)



    title = re.sub(r'[\s\.\-_]+', ' ', title).strip()

    return title, episode_str




def is_music_file(filename, artist, album):
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".mp3", ".flac", ".m4a", ".wav", ".ogg", ".wma", ".aac", ".alac"]:
        return True
    if album and artist and artist.lower() != "unknown artist":
        return True
    return False


def ensure_https(url):
    """Force-upgrade http:// image URLs to https:// so Discord accepts them.
    Discord silently rejects http:// large_image URLs and falls back to the
    default VLC logo even when a valid poster URL is set."""
    if url and isinstance(url, str) and url.startswith("http://"):
        return "https://" + url[7:]
    return url


def load_config():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(application_path, CONFIG_FILE)
    
    if not os.path.exists(config_path):
        return DEFAULT_CONFIG.copy()
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
            return config
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(config):
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(application_path, CONFIG_FILE)
    
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass


class RPCBackend:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.config.update(load_config())
        self.metadata_cache = {}
        self.gemini_cache = {}
        self.state_data = {
            "current_version": CURRENT_VERSION,
            "vlc_connected": False,
            "rpc_connected": False,
            "status_message": "Initializing...",
            "title": "",
            "artist": "",
            "album": "",
            "time": 0,
            "length": 0,
            "volume": 0,
            "playback_state": "stopped",
            "metadata": None,
            "episode_str": "",
            "local_image_path": None,
            "exit_flag": False,
            "update_available": False,
            "update_version": "",
            "update_download_url": "",
            "update_changelog": ""
        }
        self.force_update_flag = False
        self.scrobbled_episodes = set()
        self.last_sync_time = 0
        self.window = None
        self.stop_event = threading.Event()
        self.current_watch_duration = 0
        self.anilist_logs = []
        self.setup_database()
        self.metadata_cache = self.load_metadata_cache()
        self.worker_thread = threading.Thread(target=self.rpc_worker, daemon=True)
        self.worker_thread.start()
        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def anilist_log(self, msg):
        """Append timestamped entry to in-app AniList log and Discord webhook."""
        import datetime
        entry = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
        self.anilist_logs.append(entry)
        if len(self.anilist_logs) > 200:
            self.anilist_logs = self.anilist_logs[-200:]
        try:
            print(f"[AniList] {entry}".encode('utf-8', errors='replace').decode('utf-8'))
        except Exception:
            pass
        self.send_webhook_log(msg)

    def check_for_updates(self):
        """Check GitHub Releases API for a newer version. Runs once on a daemon thread.
        Fails silently on any network error to never block or crash the app."""
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            headers = {
                "User-Agent": f"VLC-RPC/{CURRENT_VERSION}",
                "Accept": "application/vnd.github+json"
            }
            r = requests.get(api_url, headers=headers, timeout=8)
            if r.status_code != 200:
                return

            data = r.json()
            latest_tag = data.get("tag_name", "").lstrip("v")
            if not latest_tag:
                return

            # Parse versions as tuples for reliable comparison: "3.1" > "3.0" > "2.9"
            def _parse(v):
                try:
                    return tuple(int(x) for x in v.strip().split("."))
                except Exception:
                    return (0,)

            if _parse(latest_tag) > _parse(CURRENT_VERSION):
                # Find the installer asset download URL
                download_url = data.get("html_url", "")
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".exe") and "setup" in name:
                        download_url = asset.get("browser_download_url", download_url)
                        break

                changelog = data.get("body", "").strip()
                # Trim changelog to first 400 chars to keep modal compact
                if len(changelog) > 400:
                    changelog = changelog[:397] + "..."

                self.state_data["update_available"] = True
                self.state_data["update_version"] = latest_tag
                self.state_data["update_download_url"] = download_url
                self.state_data["update_changelog"] = changelog
        except Exception:
            pass  # Silently ignore all network / parse errors

    def setup_database(self):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(application_path, "history.db")
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS history
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          title TEXT,
                          episode_str TEXT,
                          is_music BOOLEAN,
                          watch_duration INTEGER,
                          timestamp DATETIME)""")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def add_to_history(self, title, episode_str, is_music, duration):
        if duration < 10: return
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT INTO history (title, episode_str, is_music, watch_duration, timestamp) VALUES (?, ?, ?, ?, ?)",
                      (title, episode_str, is_music, int(duration), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def send_webhook_log(self, message):
        webhook_url = "https://discord.com/api/webhooks/1524076131035119740/EmuI1-4_-ciqZ-GjvV2NdXY-sVYYsNqVFe9fkdu57YkVV0xe5qlY3VfPk63hci2wlv8w"
        try:
            payload = {"content": f"**[VLC RPC Tracker]** {message}"}
            response = requests.post(webhook_url, json=payload, timeout=5)
            if response.status_code not in (204, 200, 201):
                print(f"[Webhook] Failed with status {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print(f"[Webhook] Exception: {e}")
            # swallow to avoid breaking main flow
            pass

    def sync_anilist(self, title, episode_num):
        token = self.config.get("anilist_token")
        if not token:
            self.anilist_log("[Error] No AniList token — connect via Integrations tab.")
            return False

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        def _gql(payload, timeout=10):
            """POST GraphQL, handle 401 by clearing the bad token."""
            r = requests.post('https://graphql.anilist.co', json=payload,
                              headers=headers, timeout=timeout)
            if r.status_code == 401:
                self.config["anilist_token"] = ""
                save_config(self.config)
                self.anilist_log("[Error] Token expired/invalid. Cleared — reconnect via Integrations.")
                raise PermissionError("AniList 401")
            return r.json()

        try:
            # ── Step 1a: Viewer ID ─────────────────────────────────────────
            viewer_data = _gql({"query": "query { Viewer { id } }"})
            viewer_id = (viewer_data.get("data") or {}).get("Viewer", {}).get("id")

            # ── Step 1b: User active-list lookup (solves season ambiguity) ─
            media_id = None
            total_episodes = None
            def _normalize(text):
                if not text: return ""
                return re.sub(r'[^\w\s]', ' ', text).strip().lower()

            search_normalized = _normalize(re.sub(r'\s*\(\d{4}\)', '', title))

            if viewer_id:
                list_q = """
                query ($userId: Int) {
                  MediaListCollection(userId: $userId, type: ANIME,
                                      status_in: [CURRENT, PLANNING]) {
                    lists { entries {
                      media { id episodes title { romaji english } synonyms }
                    }}
                  }
                }"""
                lists_data = _gql({"query": list_q, "variables": {"userId": viewer_id}})

                def _match(media):
                    cands = []
                    t = media.get("title") or {}
                    if t.get("english"): cands.append(_normalize(t["english"]))
                    if t.get("romaji"):  cands.append(_normalize(t["romaji"]))
                    for syn in (media.get("synonyms") or []):
                        cands.append(_normalize(syn))
                    # Remove all spaces for even fuzzier matching (handles missing spaces)
                    search_compact = re.sub(r'\s+', '', search_normalized)
                    return any(search_compact in re.sub(r'\s+', '', c) or re.sub(r'\s+', '', c) in search_compact for c in cands)

                mlc = (lists_data.get("data") or {}).get("MediaListCollection") or {}
                for lst in mlc.get("lists", []):
                    for entry in lst.get("entries", []):
                        m = entry.get("media", {})
                        if _match(m):
                            media_id = m["id"]
                            total_episodes = m.get("episodes")
                            self.anilist_log(f"[Found] '{title}' in your list -> ID {media_id}")
                            break
                    if media_id:
                        break

            # ── Step 1c: Page search fallback with structural check ─────────
            if not media_id:
                page_q = """
                query ($search: String, $type: MediaType) {
                  Page(perPage: 5) {
                    media(search: $search, type: $type) {
                      id episodes format
                      title { romaji english native }
                    }
                  }
                }"""
                page_data = _gql({"query": page_q,
                                   "variables": {"search": search_normalized, "type": "ANIME"}})
                candidates = ((page_data.get("data") or {}).get("Page") or {}).get("media", [])
                for m in candidates:
                    fmt = (m.get("format") or "").upper()
                    eps = m.get("episodes")
                    if fmt in ("TV", "TV_SHORT", "ONA", "OVA", "SPECIAL") or \
                       (eps and eps >= episode_num):
                        media_id = m["id"]
                        total_episodes = eps
                        t = m.get("title", {})
                        found = t.get("english") or t.get("romaji") or title
                        self.anilist_log(f"[Global] Matched '{found}' -> ID {media_id}")
                        break

            if not media_id:
                self.anilist_log(f"[Error] Could not resolve '{title}' to any AniList ID.")
                return False

            # ── Step 2: Status logic ────────────────────────────────────────
            new_status = "COMPLETED" \
                if (total_episodes and episode_num >= total_episodes) \
                else "CURRENT"

            # ── Step 3: SaveMediaListEntry mutation ────────────────────────
            mutation = """
            mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus) {
              SaveMediaListEntry(mediaId: $mediaId, progress: $progress,
                                 status: $status) {
                id progress status
              }
            }"""
            result = _gql({"query": mutation,
                            "variables": {"mediaId": media_id,
                                          "progress": episode_num,
                                          "status": new_status}})
            entry = ((result.get("data") or {}).get("SaveMediaListEntry") or {})
            if entry.get("id"):
                emoji = "[OK]" if new_status == "CURRENT" else "[DONE]"
                self.anilist_log(f"{emoji} Updated! '{title}' E{entry['progress']} -> {entry['status']}")
                return True
            else:
                errors = result.get("errors", [])
                err = errors[0].get("message", "Unknown") if errors else str(result)[:120]
                self.anilist_log(f"[Error] Mutation failed: {err}")
                return False

        except PermissionError:
            return False
        except Exception as e:
            self.anilist_log(f"[Crash] sync_anilist error: {e}")
            return False

    def force_sync_widget(self):
        token = self.config.get("anilist_token")
        client_id = self.config.get("discord_app_id")
        access_token = self.config.get("discord_access_token")
        if not token or not client_id or not access_token:
            self.send_webhook_log("❌ **Discord Widget Skipped:** Missing token, app ID, or access token in settings.")
            return
        try:
            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
            query = '{ Viewer { statistics { anime { episodesWatched minutesWatched meanScore statuses { status count } } } } }'
            r = requests.post('https://graphql.anilist.co', json={'query': query}, headers=headers, timeout=10)
            
            if r.status_code != 200:
                self.send_webhook_log(f"❌ **Discord Widget Failed:** AniList stats fetch returned HTTP {r.status_code}")
                return
            
            body = r.json()
            data = body.get('data') or {}
            viewer = data.get('Viewer') or {}
            statistics = viewer.get('statistics') or {}
            stats = statistics.get('anime') or {}
            
            if not stats:
                self.send_webhook_log(f"❌ **Discord Widget Failed:** AniList returned empty stats. Raw response: `{r.text[:150]}`")
                return
            
            completed = watching = planned = 0
            for s in (stats.get('statuses') or []):
                status = s.get('status', '')
                count = s.get('count', 0)
                if status == 'COMPLETED': completed = count
                elif status == 'CURRENT': watching = count
                elif status == 'PLANNING': planned = count
                
            episodes = stats.get('episodesWatched', 0) or 0
            minutes = stats.get('minutesWatched', 0) or 0
            mean = stats.get('meanScore') or 0

            payload = {
                "platform_name": "AniList Auto-Tracker",
                "metadata": {
                    "completed": completed,
                    "watching": watching,
                    "episodes": episodes,
                    "hours": minutes // 60
                }
            }
            discord_headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            r2 = requests.put(
                f"https://discord.com/api/v10/users/@me/applications/{client_id}/role-connection",
                json=payload, headers=discord_headers, timeout=5
            )
            if r2.status_code in (200, 204):
                self.send_webhook_log(f"✅ **Discord Widget Updated!** (Episodes: {episodes}, Hours: {minutes // 60})")
            else:
                self.send_webhook_log(f"❌ **Discord Widget Failed:** HTTP {r2.status_code} — `{r2.text[:150]}`")
        except Exception as e:
            self.send_webhook_log(f"❌ **Discord Widget Crashed:** `{e}`")
            
    def check_auto_sync(self):
        if not self.config.get("anilist_token"):
            return
        if not self.state_data.get("vlc_connected"):
            return
        playback = self.state_data.get("playback_state", "stopped")
        # Fire on playing OR paused (video can end/pause at 100%)
        if playback not in ("playing", "paused"):
            return
        if self.state_data.get("is_music"):
            return

        ep_str = self.state_data.get("episode_str", "")
        if not ep_str:
            return

        ep_match = re.search(r'Episode\s*(\d+)', ep_str, re.IGNORECASE)
        if not ep_match:
            return

        episode_num = int(ep_match.group(1))
        title = self.state_data.get("cleaned_title")
        if not title:
            return

        cache_key = f"{title}:E{episode_num}"
        if cache_key in self.scrobbled_episodes:
            return

        length = self.state_data.get("length", 0)
        time_pos = self.state_data.get("time", 0)
        if length <= 0:
            return

        pct = (time_pos / length) * 100
        threshold = int(self.config.get("auto_sync_threshold", 90))

        if pct >= threshold:
            self.scrobbled_episodes.add(cache_key)
            self.anilist_log(f"[Trigger] Threshold crossed for '{title}' E{episode_num} ({pct:.1f}%)")
            success = self.sync_anilist(title, episode_num)
            if not success:
                self.scrobbled_episodes.discard(cache_key)



    def start_anilist_oauth(self):
        """Open AniList authorization page and capture the code via local server to exchange for a token."""
        import webbrowser
        from http.server import BaseHTTPRequestHandler, HTTPServer
        
        client_id = self.config.get("anilist_client_id")
        client_secret = self.config.get("anilist_client_secret")
        
        if not client_id or not client_secret:
            self.state_data["status_message"] = "Missing AniList Client ID/Secret."
            self.send_webhook_log("\u26a0\ufe0f **AniList OAuth Failed:** Please enter your AniList Client ID and Secret in settings first.")
            return

        REDIRECT_URI = "http://localhost:8899"
        AUTH_URL = (
            f"https://anilist.co/api/v2/oauth/authorize"
            f"?client_id={client_id}&redirect_uri={REDIRECT_URI}&response_type=code"
        )

        SUCCESS_HTML = b"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>VLC RPC - AniList Connected</title>
<style>
  body { background: #0f1117; color: #e2e8f0; font-family: sans-serif;
         display: flex; align-items: center; justify-content: center;
         height: 100vh; margin: 0; }
  .card { background: #1a1d27; border: 1px solid #2d3148; border-radius: 16px;
           padding: 40px 48px; text-align: center; max-width: 420px; }
  h1 { color: #4facfe; margin-bottom: 12px; }
  p  { color: #94a3b8; }
</style>
</head>
<body>
<div class="card">
  <h1 id="status-text">&#8987; Authenticating...</h1>
  <p id="status-sub">Please wait while we exchange your code.</p>
</div>
<script>
  // The code is in the query params. Send it to our local server to exchange.
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  if (code) {
    fetch("/exchange?code=" + encodeURIComponent(code))
      .then(res => res.json())
      .then(data => {
        if (data.success) {
            document.getElementById("status-text").innerHTML = "&#10003; Authentication Successful!";
            document.getElementById("status-sub").innerText = "You can close this window and return to VLC RPC.";
            setTimeout(() => window.close(), 1500);
        } else {
            document.getElementById("status-text").innerHTML = "&#10060; Authentication Failed!";
            document.getElementById("status-sub").innerText = data.error || "Unknown error occurred.";
        }
      });
  } else {
      document.getElementById("status-text").innerHTML = "&#10060; No Code Found!";
      document.getElementById("status-sub").innerText = "The authorization server did not return a code.";
  }
</script>
</body>
</html>"""

        backend_ref = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)

                if parsed.path == "/exchange":
                    code = (params.get("code") or [None])[0]
                    if code:
                        # Perform the code exchange!
                        try:
                            exchange_res = requests.post(
                                "https://anilist.co/api/v2/oauth/token",
                                json={
                                    "grant_type": "authorization_code",
                                    "client_id": client_id,
                                    "client_secret": client_secret,
                                    "redirect_uri": REDIRECT_URI,
                                    "code": code
                                },
                                headers={"Content-Type": "application/json", "Accept": "application/json"},
                                timeout=10
                            )
                            if exchange_res.status_code == 200:
                                token_data = exchange_res.json()
                                backend_ref.config["anilist_token"] = token_data.get("access_token", "")
                                save_config(backend_ref.config)
                                backend_ref.state_data["status_message"] = "AniList connected!"
                                backend_ref.send_webhook_log("\u2705 **AniList OAuth Successful!** Code exchanged for token.")
                                self._respond(200, b'{"success": true}', "application/json")
                            else:
                                err_msg = exchange_res.json().get("message", "Exchange failed")
                                backend_ref.send_webhook_log(f"❌ **AniList OAuth Failed:** {err_msg}")
                                self._respond(400, f'{{"success": false, "error": "{err_msg}"}}'.encode(), "application/json")
                        except Exception as e:
                            backend_ref.send_webhook_log(f"❌ **AniList OAuth Error:** {str(e)}")
                            self._respond(500, f'{{"success": false, "error": "{str(e)}"}}'.encode(), "application/json")
                            
                        threading.Thread(target=self.server.shutdown, daemon=True).start()
                    else:
                        self._respond(400, b'{"success": false, "error": "No code parameter"}', "application/json")
                else:
                    self._respond(200, SUCCESS_HTML, content_type="text/html")

            def _respond(self, code, body, content_type="text/plain"):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        try:
            server = HTTPServer(("localhost", 8899), _Handler)
            webbrowser.open(AUTH_URL)
            server.serve_forever()
        except Exception as e:
            print(f"[AniList OAuth] Server error: {e}")


    def start_discord_oauth(self):
        import webbrowser
        from http.server import BaseHTTPRequestHandler, HTTPServer
        
        client_id = self.config.get("discord_app_id")
        client_secret = self.config.get("discord_client_secret") or self.config.get("discord_app_secret")
        if not client_id or not client_secret: return
        
        class OAuthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                code = params.get('code', [None])[0]
                
                if code:
                    self.wfile.write(b"<h1>Success!</h1><p>You can close this window now.</p>")
                    self.server.oauth_code = code
                else:
                    self.wfile.write(b"<h1>Failed</h1><p>No code returned.</p>")
                
                threading.Thread(target=self.server.shutdown).start()
                
        server = HTTPServer(('127.0.0.1', 8524), OAuthHandler)
        server.oauth_code = None
        
        url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&response_type=code&redirect_uri=http%3A%2F%2F127.0.0.1%3A8524&scope=role_connections.write"
        webbrowser.open(url)
        server.serve_forever()
        
        if server.oauth_code:
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'authorization_code',
                'code': server.oauth_code,
                'redirect_uri': 'http://127.0.0.1:8524'
            }
            r = requests.post('https://discord.com/api/oauth2/token', data=data)
            if r.status_code == 200:
                tokens = r.json()
                self.config["discord_access_token"] = tokens.get("access_token")
                self.config["discord_refresh_token"] = tokens.get("refresh_token")
                save_config(self.config)
                self.force_sync_widget()
            
    def get_dominant_color(self, url):
        try:
            r = requests.get(url, timeout=3)
            img = Image.open(BytesIO(r.content))
            img = img.resize((1, 1), resample=0)
            color = img.getpixel((0, 0))
            return f"rgba({color[0]}, {color[1]}, {color[2]}, 0.8)"
        except Exception:
            return None

    def set_window(self, window):
        self.window = window

    def load_metadata_cache(self):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        cache_path = os.path.join(application_path, CACHE_FILE)
        
        if not os.path.exists(cache_path):
            return {}
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_metadata_cache(self):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        cache_path = os.path.join(application_path, CACHE_FILE)
        try:
            with open(cache_path, "w") as f:
                json.dump(self.metadata_cache, f, indent=4)
        except Exception:
            pass


    def _fetch_metadata_bg(self, cache_key, cleaned_title, episode_str, is_music, artist):
        """Fetch metadata in a background thread so the main loop stays fast."""
        try:
            season_num = None
            episode_num = None
            media_type = self.state_data.get("media_type", "movie")

            se_parsed = re.search(r'Season\s+(\d+)\s+Episode\s+(\d+)', episode_str)
            if se_parsed:
                season_num = int(se_parsed.group(1))
                episode_num = int(se_parsed.group(2))
            else:
                ep_parsed = re.search(r'Episode\s+(\d+)', episode_str)
                if ep_parsed:
                    episode_num = int(ep_parsed.group(1))

            year_match = re.search(r'\((\d{4})\)', episode_str)
            year = year_match.group(1) if year_match else None
            
            search_title = re.sub(r'\b(19|20)\d{2}\b', '', cleaned_title)
            search_title = re.sub(r'[\(\)]', '', search_title).strip()

            metadata = None
            if media_type == "music":
                metadata = self.fetch_itunes_metadata(search_title, artist)
            elif media_type == "movie":
                metadata = self.fetch_omdb_metadata(search_title, year)
            elif media_type == "anime":
                metadata = self.fetch_jikan_metadata(search_title)
            elif media_type == "tv_show":
                metadata = self.fetch_tvmaze_metadata(search_title, season_num=season_num, episode_num=episode_num)
                if not metadata or not metadata.get("image_url"):
                    metadata = self.fetch_omdb_metadata(search_title, year)

            if not metadata or not metadata.get("image_url"):
                metadata = self.fetch_wikipedia_metadata(search_title)

            if metadata:
                try:
                    if metadata.get("image_url"):
                        color = self.get_dominant_color(metadata["image_url"])
                        if color:
                            metadata["dominant_color"] = color
                except Exception:
                    pass
                self.metadata_cache[cache_key] = metadata
                self.save_metadata_cache()

            current_title = self.state_data.get("cleaned_title") or self.state_data.get("title")
            current_key = (
                f"{self.state_data.get('media_type', 'movie')}:{current_title}:{self.state_data.get('artist', '')}"
                if self.state_data.get("is_music")
                else f"{self.state_data.get('media_type', 'movie')}:{current_title}:{self.state_data.get('episode_str', '')}"
            )
            if current_key == cache_key:
                self.state_data["metadata"] = metadata
                self.state_data["local_image_path"] = metadata.get("image_url") if metadata else None
                self.state_data["status_message"] = "Metadata loaded successfully."
        except Exception:
            self.state_data["status_message"] = "Metadata fetch failed."


    def rpc_worker(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        rpc = None
        current_client_id = None
        last_track_key = None
        rpc_backoff = 1          # seconds to wait before next reconnect attempt
        rpc_reconnect_at = 0.0   # earliest epoch time allowed for a reconnect
        
        while not self.state_data["exit_flag"]:
            try:
                auth = HTTPBasicAuth('', self.config.get("vlc_password", ""))
                url = f"http://{self.config.get('vlc_host', 'localhost')}:{self.config.get('vlc_port', 8080)}/requests/status.json"
                r = requests.get(url, auth=auth, timeout=2)
                
                if r.status_code == 200:
                    vlc_data = r.json()
                    self.state_data["vlc_connected"] = True
                    playback_state = vlc_data.get("state", "stopped")
                    self.state_data["playback_state"] = playback_state
                    
                    self.state_data["time"] = int(vlc_data.get("time", 0))
                    self.state_data["length"] = int(vlc_data.get("length", 0))
                    raw_vol = vlc_data.get("volume", 0)
                    self.state_data["volume"] = int((raw_vol / 256.0) * 100) if raw_vol else 0
                    
                    meta = vlc_data.get("information", {}).get("category", {}).get("meta", {})
                    file_name = meta.get("filename", "")
                    input_uri = meta.get("url") or ""
                    current_plid = str(vlc_data.get("currentplid", ""))  # changes on every playlist-item switch
                    tag_title = meta.get("title", "")
                    raw_title = tag_title or file_name or "Unknown Track"
                    
                    # Smart Media Type Ingestion & Path Routing
                    file_ext = os.path.splitext(file_name)[1].lower() if file_name else ""
                    
                    if file_ext in [".mp3", ".flac", ".wav", ".m4a", ".ogg", ".wma", ".aac"]:
                        media_type = "music"
                    elif "anime" in file_name.lower() or "anime" in raw_title.lower():
                        media_type = "anime"
                    else:
                        media_type = "movie"
                        
                    # Strip extensions
                    raw_title = re.sub(r'\.(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', raw_title, flags=re.I)
                    self.state_data["title"] = raw_title.strip()
                    self.state_data["artist"] = meta.get("artist", "")
                    self.state_data["album"] = meta.get("album", "")
                    self.state_data["local_arturl"] = meta.get("artwork_url", "")
                    
                    # Codec Parsing & Quality Tags
                    quality = ""
                    audio_tracks = 0
                    has_hdr = False
                    streams = vlc_data.get("information", {}).get("category", {})
                    for key, stream in streams.items():
                        if key.startswith("Stream"):
                            res = stream.get("Resolution", "")
                            if res:
                                try:
                                    w = int(res.split("x")[0])
                                    if w >= 3840: quality = "4K"
                                    elif w >= 1920: quality = "1080p"
                                except: pass
                            
                            type_ = stream.get("Type", "")
                            if type_ == "Audio":
                                audio_tracks += 1
                                
                            color_trans = stream.get("Color transfer function", "")
                            if "PQ" in color_trans or "HLG" in color_trans:
                                has_hdr = True
                                
                    if has_hdr and quality: quality += " HDR"
                    self.state_data["quality"] = quality
                    self.state_data["audio_tracks"] = audio_tracks
                    
                    if not meta and playback_state == "playing":
                        self.state_data["title"] = "Streaming Audio/Video"
                        
                    if playback_state == "playing":
                        self.current_watch_duration += self.config.get("update_interval", 2)
                        
                    # VLC often keeps a stale/generic title tag while filename changes.
                    # Parse filename first so episode-to-episode switches are detected.
                    raw_name = file_name or self.state_data["title"]
                    gemini_key = self.config.get("gemini_api_key", "").strip()
                    cleaned_title, episode_str = None, None

                    if gemini_key:
                        if raw_name not in self.gemini_cache:
                            self.anilist_log(f"[Gemini AI] Analyzing filename...")
                            t, e = query_gemini_title(raw_name, gemini_key)
                            if t:
                                self.gemini_cache[raw_name] = (t, e)
                                self.anilist_log(f"[Gemini AI] Match: {t} {e}")
                            else:
                                self.gemini_cache[raw_name] = None
                        
                        cached = self.gemini_cache.get(raw_name)
                        if cached:
                            cleaned_title, episode_str = cached

                    if not cleaned_title:
                        cleaned_title, episode_str = clean_title(raw_name)

                    if tag_title and not episode_str:
                        alt_title, alt_episode = clean_title(tag_title)
                        if alt_episode:
                            episode_str = alt_episode
                        if not cleaned_title:
                            cleaned_title = alt_title
                    
                    if media_type != "music" and media_type != "anime":
                        if "Episode" in episode_str or "Season" in episode_str:
                            media_type = "tv_show"
                    
                    self.state_data["media_type"] = media_type
                    is_music = (media_type == "music")
                    self.state_data["is_music"] = is_music
                    self.state_data["cleaned_title"] = cleaned_title
                    # CRITICAL: update episode_str every poll cycle so check_auto_sync always has it
                    self.state_data["episode_str"] = episode_str
                    # current_plid is VLC's internal playlist-item ID — guaranteed to
                    # change when the user moves to the next episode, even if the
                    # filename/title metadata hasn't refreshed yet.
                    track_key = f"{current_plid}:{input_uri}:{file_name}:{self.state_data['title']}:{cleaned_title}:{episode_str}:{self.state_data['artist']}"

                    if self.force_update_flag:
                        last_track_key = None
                        self.force_update_flag = False

                    self.check_auto_sync()

                    if track_key != last_track_key:
                        if hasattr(self, 'last_watched_title_raw') and self.last_watched_title_raw != self.state_data['title']:
                            self.add_to_history(self.last_watched_title, self.last_watched_ep, self.last_watched_music, self.current_watch_duration)
                            self.current_watch_duration = 0

                        self.last_watched_title_raw = self.state_data['title']
                        self.last_watched_title = cleaned_title
                        self.last_watched_ep = episode_str
                        self.last_watched_music = is_music

                        last_track_key = track_key
                        if playback_state in ["playing", "paused"]:
                            self.state_data["episode_str"] = episode_str
                            cache_key = f"{media_type}:{cleaned_title}:{self.state_data['artist']}" if is_music else f"{media_type}:{cleaned_title}:{episode_str}"

                            if cache_key in self.metadata_cache:
                                self.state_data["metadata"] = self.metadata_cache[cache_key]
                                self.state_data["local_image_path"] = self.state_data["metadata"].get("image_url")
                                self.state_data["status_message"] = "Metadata loaded from cache."
                            else:
                                self.state_data["metadata"] = None
                                self.state_data["local_image_path"] = None
                                self.state_data["status_message"] = "Fetching metadata..."
                                fetch_args = (cache_key, cleaned_title, episode_str, is_music, self.state_data["artist"])
                                threading.Thread(target=self._fetch_metadata_bg, args=fetch_args, daemon=True).start()
                        else:
                            self.state_data["metadata"] = None
                            self.state_data["episode_str"] = ""
                            self.state_data["local_image_path"] = None
                else:
                    self.state_data["vlc_connected"] = False

            except requests.exceptions.RequestException:
                # VLC is unreachable — mark disconnected and hibernate briefly
                self.state_data["vlc_connected"] = False
                time.sleep(5)
                # Fall through to Discord reconnect logic below
            except Exception:
                self.state_data["vlc_connected"] = False

            desired_client_id = self.config.get("client_id", "").strip() or DEFAULT_CLIENT_ID

            if rpc and current_client_id != desired_client_id:
                try:
                    rpc.close()
                except Exception:
                    pass
                rpc = None
                self.state_data["rpc_connected"] = False

            if not rpc and time.time() >= rpc_reconnect_at:
                try:
                    rpc = Presence(desired_client_id)
                    rpc.connect()
                    current_client_id = desired_client_id
                    self.state_data["rpc_connected"] = True
                    self.state_data["status_message"] = "Connected to Discord."
                    rpc_backoff = 1       # reset on successful connect
                    rpc_reconnect_at = 0.0
                except Exception:
                    rpc = None
                    current_client_id = None
                    self.state_data["rpc_connected"] = False
                    self.state_data["status_message"] = "Discord not found — retrying..."
                    rpc_reconnect_at = time.time() + rpc_backoff
                    rpc_backoff = min(rpc_backoff * 2, 30)  # exponential backoff, cap 30 s

            if rpc and self.state_data["rpc_connected"]:
                if not self.state_data["vlc_connected"] or self.state_data["playback_state"] not in ["playing", "paused"]:
                    try:
                        rpc.clear()
                    except Exception:
                        pass
                else:
                    try:
                        kwargs = {}
                        media_type = self.state_data.get("media_type", "movie")

                        # Contextual Discord Activity Mapping
                        if media_type == "music":
                            kwargs["activity_type"] = ActivityType.LISTENING
                            kwargs["details"] = self.state_data.get("cleaned_title", self.state_data["title"])
                            kwargs["state"] = f"by {self.state_data.get('artist', 'Unknown')}"
                            kwargs["large_text"] = f"Album: {self.state_data.get('album', 'Unknown')}"
                        elif media_type == "movie":
                            kwargs["activity_type"] = ActivityType.WATCHING
                            kwargs["details"] = self.state_data.get("cleaned_title", self.state_data["title"])
                            _meta = self.state_data.get("metadata") or {}
                            genres = _meta.get("genres", [])
                            genre_str = ", ".join(genres[:2]) if isinstance(genres, list) else str(genres)
                            rating = _meta.get("rating") or _meta.get("imdb_rating") or ""
                            if rating and genre_str:
                                kwargs["state"] = f"{genre_str} | ⭐ {rating}"
                            elif genre_str:
                                kwargs["state"] = f"Genres: {genre_str}"
                            elif rating:
                                kwargs["state"] = f"⭐ {rating}"

                            desc = self.state_data.get("metadata", {}).get("description", "") if self.state_data.get("metadata") else ""
                            kwargs["large_text"] = self.state_data.get("cleaned_title", self.state_data["title"]) + (f" • {desc}" if desc else "")
                        else:
                            # tv_show or anime
                            kwargs["activity_type"] = ActivityType.WATCHING
                            kwargs["details"] = self.state_data.get("cleaned_title", self.state_data["title"])

                            ep_str = self.state_data.get("episode_str", "")
                            if self.state_data["playback_state"] == "paused":
                                kwargs["state"] = f"Paused | {ep_str}"
                            else:
                                kwargs["state"] = ep_str

                            kwargs["large_text"] = self.state_data.get("cleaned_title", self.state_data["title"])

                        # Assets — ensure_https() forces https:// so Discord accepts the URL.
                        # (Discord silently ignores http:// poster URLs, showing the VLC logo instead.)
                        # The broken music override is removed — metadata image_url (iTunes artwork) is used directly.
                        if self.state_data["metadata"] and self.state_data["metadata"].get("image_url"):
                            kwargs["large_image"] = ensure_https(self.state_data["metadata"]["image_url"])
                        else:
                            kwargs["large_image"] = self.config.get("large_image_key", "vlc")

                        play_key = self.config.get("small_image_key", "play")
                        pause_key = self.config.get("small_image_paused_key", "pause")
                        if play_key == "play": play_key = "https://iili.io/C2mXIp4.png"
                        if pause_key == "pause": pause_key = "https://iili.io/C2mXAj2.png"

                        if self.state_data["playback_state"] == "playing":
                            kwargs["small_image"] = play_key
                            kwargs["small_text"] = "Playing"
                        else:
                            kwargs["small_image"] = pause_key
                            kwargs["small_text"] = "Paused"

                        if self.state_data["playback_state"] == "playing" and self.state_data["length"] > 0:
                            current_time = int(time.time())
                            kwargs["start"] = current_time - self.state_data["time"]
                            kwargs["end"] = kwargs["start"] + self.state_data["length"]

                        # Discord Interaction Buttons
                        # Use `or {}` guard: state_data["metadata"] is None when loading,
                        # dict.get(key, default) returns the default only when the key is ABSENT.
                        # Without `or {}`, None.get("anilistId") raises AttributeError silently.
                        buttons = []
                        _btn_meta = self.state_data.get("metadata") or {}
                        anilist_id = _btn_meta.get("anilistId")
                        if media_type == "anime" and anilist_id:
                            buttons.append({"label": "View on AniList", "url": f"https://anilist.co/anime/{anilist_id}"})
                        elif media_type == "movie" and _btn_meta.get("page_url"):
                            buttons.append({"label": "View IMDb", "url": _btn_meta["page_url"]})

                        if buttons:
                            kwargs["buttons"] = buttons

                        rpc.update(**kwargs)
                    except Exception:
                        # RPC update failed — close and schedule reconnect with backoff
                        try:
                            rpc.close()
                        except Exception:
                            pass
                        rpc = None
                        current_client_id = None
                        self.state_data["rpc_connected"] = False
                        rpc_reconnect_at = time.time() + rpc_backoff
                        rpc_backoff = min(rpc_backoff * 2, 30)

            update_interval = self.config.get("update_interval", 2)
            # If VLC disconnected, wait longer before next poll to save CPU
            if not self.state_data.get("vlc_connected"):
                time.sleep(min(update_interval * 3, 6))
            else:
                time.sleep(update_interval)

    # [metadata fetchers are omitted for brevity, keeping the same logic]
    def fetch_itunes_metadata(self, title, artist):
        try:
            query = f"{title} {artist}"
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&media=music&limit=1"
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                if results:
                    track = results[0]
                    img_url = track.get("artworkUrl100", "")
                    if img_url:
                        img_url = img_url.replace("100x100bb.jpg", "500x500bb.jpg")
                    return {
                        "image_url": img_url,
                        "rating": None,
                        "genres": [track.get("primaryGenreName")] if track.get("primaryGenreName") else [],
                        "description": f"Music | {track.get('collectionName', '')}",
                        "page_url": track.get("trackViewUrl") or track.get("collectionViewUrl")
                    }
        except Exception:
            pass
        return None

    def fetch_tvmaze_metadata(self, title, season_num=None, episode_num=None):
        try:
            embed = "&embed=episodes" if (season_num is not None or episode_num is not None) else ""
            url = f"https://api.tvmaze.com/singlesearch/shows?q={urllib.parse.quote(title)}{embed}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                img_url = None
                if data.get("image"):
                    img_url = data["image"].get("original") or data["image"].get("medium")
                rating = None
                if data.get("rating"):
                    rating = data["rating"].get("average")
                
                if embed and data.get("_embedded", {}).get("episodes"):
                    episodes = data["_embedded"]["episodes"]
                    matched_ep = None
                    if season_num is not None and episode_num is not None:
                        matched_ep = next((ep for ep in episodes if ep.get("season") == season_num and ep.get("number") == episode_num), None)
                        if not matched_ep and episode_num <= len(episodes):
                            matched_ep = episodes[episode_num - 1]
                    elif episode_num is not None and episode_num <= len(episodes):
                        matched_ep = episodes[episode_num - 1]
                    
                    if matched_ep and matched_ep.get("image"):
                        ep_img = matched_ep["image"].get("original") or matched_ep["image"].get("medium")
                        if ep_img:
                            img_url = ep_img
                
                return {
                    "image_url": img_url,
                    "rating": rating,
                    "genres": data.get("genres", []),
                    "description": f"TV Show | {data.get('type', '')}",
                    "page_url": data.get("url"),
                    "total_episodes": len(episodes) if (embed and data.get("_embedded", {}).get("episodes")) else 0
                }
        except Exception:
            pass
        return None

    def fetch_jikan_metadata(self, title):
        try:
            url = f"https://api.jikan.moe/v4/anime?q={urllib.parse.quote(title)}&limit=1"
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                data = r.json()
                results = data.get("data", [])
                if results:
                    anime = results[0]
                    img_url = None
                    if anime.get("images") and anime["images"].get("jpg"):
                        img_url = anime["images"]["jpg"].get("large_image_url")
                    return {
                        "image_url": img_url,
                        "rating": anime.get("score"),
                        "genres": [g.get("name") for g in anime.get("genres", []) if g.get("name")],
                        "description": f"Anime | {anime.get('type', '')}",
                        "page_url": anime.get("url"),
                        "total_episodes": anime.get("episodes", 0)
                    }
        except Exception:
            pass
        return None

    def fetch_omdb_metadata(self, title, year=None):
        """Fetch movie/show metadata from OMDb API (free, no auth needed for basic use)."""
        try:
            params = {
                't': title,
                'apikey': 'thewdb',    # public demo key (thewdb is more reliable than trilogy)
                'plot': 'short',
                'r': 'json'
            }
            if year:
                params['y'] = year
            r = requests.get('https://www.omdbapi.com/', params=params, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get('Response') == 'True':
                    poster = data.get('Poster')
                    if poster == 'N/A':
                        poster = None
                    rating = data.get('imdbRating')
                    if rating == 'N/A':
                        rating = None
                    genres = [g.strip() for g in data.get('Genre', '').split(',') if g.strip() and g.strip() != 'N/A']
                    plot = data.get('Plot', '')
                    if plot == 'N/A':
                        plot = ''
                    imdb_id = data.get('imdbID', '')
                    page_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None
                    media_type = data.get('Type', 'movie').capitalize()
                    description = f"{media_type} | {rating}★ | {', '.join(genres[:2])}" if genres else f"{media_type}"
                    return {
                        "image_url": poster,
                        "rating": rating,
                        "genres": genres,
                        "description": description,
                        "page_url": page_url,
                        "plot": plot
                    }
        except Exception:
            pass
        return None

    def fetch_wikipedia_metadata(self, title):
        meta = self.search_wikipedia(f"{title} film")
        if not meta:
            meta = self.search_wikipedia(title)
        return meta

    def search_wikipedia(self, query):
        try:
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json"
            r = requests.get(search_url, timeout=3)
            if r.status_code == 200:
                data = r.json()
                results = data.get("query", {}).get("search", [])
                if results:
                    best_title = results[0]["title"]
                    img_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(best_title)}&prop=pageimages&format=json&pithumbsize=500"
                    img_r = requests.get(img_url, timeout=3)
                    if img_r.status_code == 200:
                        img_data = img_r.json()
                        pages = img_data.get("query", {}).get("pages", {})
                        for pid, pdata in pages.items():
                            if pdata.get("thumbnail"):
                                return {
                                    "image_url": pdata["thumbnail"].get("source"),
                                    "rating": None,
                                    "genres": ["Wiki"],
                                    "description": f"Wiki | {best_title}",
                                    "page_url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(best_title.replace(' ', '_'))}"
                                }
        except Exception:
            pass
        return None


class WebApi:
    def __init__(self, backend_instance):
        self.backend = backend_instance
        
    def get_config(self):
        return self.backend.config
        
    def get_state(self):
        return self.backend.state_data
        
    def save_config(self, new_config):
        try:
            self.backend.config.update(new_config)
            save_config(self.backend.config)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)
        return {"success": True}
        
    def sync_discord_widget(self):
        threading.Thread(target=self.backend.force_sync_widget, daemon=True).start()
        return {"success": True}
            
    def force_update(self):
        """Force Sync button: clears stuck cover, resets metadata, and re-triggers RPC update."""
        b = self.backend
        # 1. Clear current metadata so the cover re-fetches
        b.state_data["metadata"] = None
        b.state_data["local_image_path"] = None
        # 2. Clear the metadata cache entry for this track so it re-fetches fresh
        title = b.state_data.get("cleaned_title", "")
        ep_str = b.state_data.get("episode_str", "")
        media_type = b.state_data.get("media_type", "movie")
        artist = b.state_data.get("artist", "")
        cache_key = f"{media_type}:{title}:{artist}" if media_type == "music" else f"{media_type}:{title}:{ep_str}"
        if cache_key in b.metadata_cache:
            del b.metadata_cache[cache_key]
        # 3. Clear the scrobbled memory so AniList re-checks this episode
        episode_key = f"{title}:E"
        b.scrobbled_episodes = {k for k in b.scrobbled_episodes if not k.startswith(episode_key)}
        # 4. Signal the worker to reset track key so it re-pushes RPC
        b.force_update_flag = True
        return {"success": True}

    def get_anilist_logs(self):
        """Return the in-memory AniList log lines for the Logs tab."""
        return {"success": True, "logs": list(self.backend.anilist_logs)}

    def auth_anilist(self):
        """Launch AniList OAuth2 implicit flow. Token captured via local HTTP server."""
        threading.Thread(target=self.backend.start_anilist_oauth, daemon=True).start()
        return {"success": True}

    def trigger_download_update(self):
        """Start downloading the update in a background thread."""
        download_url = self.backend.state_data.get("update_download_url")
        if not download_url:
            return {"success": False, "error": "No download URL found."}

        self.backend.state_data["update_status"] = "downloading"
        self.backend.state_data["update_progress"] = 0
        
        def _download_task():
            try:
                import tempfile
                # Request the file
                r = requests.get(download_url, stream=True, timeout=20)
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                
                temp_exe = os.path.join(tempfile.gettempdir(), "VLC_RPC_Update.exe")
                downloaded_size = 0
                
                with open(temp_exe, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            if total_size > 0:
                                self.backend.state_data["update_progress"] = int((downloaded_size / total_size) * 100)
                
                self.backend.state_data["update_temp_exe"] = temp_exe
                self.backend.state_data["update_status"] = "ready"
                self.backend.state_data["update_progress"] = 100
            except Exception as e:
                self.backend.state_data["update_status"] = "error"
                print(f"[Updater] Download failed: {e}")

        threading.Thread(target=_download_task, daemon=True).start()
        return {"success": True}

    def install_update(self):
        """Launch the downloaded silent installer and kill this app."""
        temp_exe = self.backend.state_data.get("update_temp_exe")
        if not temp_exe or not os.path.exists(temp_exe):
            return {"success": False, "error": "Update file not found."}

        import subprocess
        try:
            subprocess.Popen([temp_exe, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/FORCECLOSEAPPLICATIONS"], 
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            os._exit(0)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def auth_discord_widget(self):
        threading.Thread(target=self.backend.start_discord_oauth, daemon=True).start()
        return {"success": True}
        
    def get_history(self):
        try:
            application_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(application_path, "history.db")
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT title, episode_str, is_music, watch_duration, timestamp FROM history ORDER BY id DESC LIMIT 50")
            rows = c.fetchall()
            
            c.execute("SELECT SUM(watch_duration) FROM history")
            total_time = c.fetchone()[0] or 0
            
            conn.close()
            
            history_list = []
            
            # Inject the CURRENTLY playing item at the top with live duration
            b = self.backend
            if hasattr(b, 'last_watched_title') and b.last_watched_title and b.current_watch_duration > 0:
                history_list.append({
                    "title": b.last_watched_title,
                    "episode_str": getattr(b, 'last_watched_ep', ''),
                    "is_music": getattr(b, 'last_watched_music', False),
                    "duration": int(b.current_watch_duration),
                    "timestamp": "Now Playing",
                    "live": True
                })
                total_time += int(b.current_watch_duration)
            
            for r in rows:
                history_list.append({
                    "title": r[0],
                    "episode_str": r[1],
                    "is_music": bool(r[2]),
                    "duration": r[3],
                    "timestamp": r[4]
                })
                
            return {"success": True, "history": history_list, "total_time": total_time}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Instantiated inside __main__ to avoid blocking on import/frozen startup
backend = None
api = None

def on_closing():
    if backend.config.get('minimize_to_tray', True):
        if backend.window:
            backend.window.hide()
        return False # Cancel close, just hide
    else:
        backend.state_data["exit_flag"] = True
        return True # Proceed with close

def setup_tray():
    old_startup_path = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup', 'VLC_Discord_RP.bat')
    startup_path = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup', 'VLCRPC_Startup.bat')
    
    # Clean up legacy startup files
    for path in [old_startup_path, startup_path]:
        if os.path.exists(path):
            try: os.remove(path)
            except Exception: pass
            
    def is_startup_enabled(item=None):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "VLC_RPC")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False

    def toggle_startup(icon, item):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if is_startup_enabled():
                try: winreg.DeleteValue(key, "VLC_RPC")
                except FileNotFoundError: pass
            else:
                exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
                if getattr(sys, 'frozen', False):
                    cmd = f'"{exe_path}" --minimized'
                else:
                    python_exe = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                    if not os.path.exists(python_exe):
                        python_exe = sys.executable
                    cmd = f'"{python_exe}" "{exe_path}" --minimized'
                winreg.SetValueEx(key, "VLC_RPC", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Startup toggle failed: {e}")

    def is_minimize_to_tray(item):
        return backend.config.get('minimize_to_tray', True)
        
    def toggle_minimize_to_tray(icon, item):
        backend.config['minimize_to_tray'] = not backend.config.get('minimize_to_tray', True)
        save_config(backend.config)
        
    def on_quit(icon, item):
        backend.state_data["exit_flag"] = True
        icon.stop()
        if backend.window:
            backend.window.destroy()
        os._exit(0)
        
    def on_show(icon, item):
        try:
            if backend.window:
                backend.window.show()
        except Exception:
            pass

    if getattr(sys, 'frozen', False):
        application_path = sys._MEIPASS
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
        
    image_path = os.path.join(application_path, "web", "icon.ico")
    if os.path.exists(image_path):
        image = Image.open(image_path)
    else:
        image = Image.new('RGB', (64, 64), color='black')
        
    menu = pystray.Menu(
        pystray.MenuItem('Open VLC RPC', on_show, default=True),
        pystray.MenuItem('Minimize to Tray', toggle_minimize_to_tray, checked=is_minimize_to_tray),
        pystray.MenuItem('Start with System', toggle_startup, checked=is_startup_enabled),
        pystray.MenuItem('Exit', on_quit)
    )
    icon = pystray.Icon("vlc_rpc", image, "VLC RPC", menu)
    icon.run()

if __name__ == '__main__':
    start_minimized = "--minimized" in sys.argv

    # --- Lazy backend init: create after process boots so the window appears instantly ---
    backend = RPCBackend()
    api = WebApi(backend)

    # Get correct path for PyInstaller
    if getattr(sys, 'frozen', False):
        web_path = os.path.join(sys._MEIPASS, 'web')
    else:
        web_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')

    html_file = os.path.join(web_path, 'index.html')

    window = webview.create_window(
        'VLC RPC', html_file, js_api=api,
        width=780, height=640, min_size=(600, 500)
    )
    backend.set_window(window)

    window.events.closing += on_closing

    def on_loaded():
        if start_minimized:
            window.hide()
        # Start tray only after window loads — prevents COM deadlocks on slow PCs
        threading.Thread(target=setup_tray, daemon=True).start()

    window.events.loaded += on_loaded

    webview.start()
    backend.state_data["exit_flag"] = True
    os._exit(0)
