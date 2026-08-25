import sys


if len(sys.argv) > 1 and sys.argv[1] == "--notifier":


    import notifier_worker


    notifier_worker.main()


    sys.exit(0)





import os


import time


import json


import threading


import re


import urllib.parse


import hashlib


import unicodedata


from difflib import SequenceMatcher


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


from PIL import Image





class NotifierClient:


    def __init__(self):


        self.proc = None


        self._start()





    def _start(self):


        try:


            import subprocess


            cmd = [sys.executable, "--notifier"]


            # CREATE_NO_WINDOW = 0x08000000 ensures no console window pops up


            self.proc = subprocess.Popen(


                cmd,


                stdin=subprocess.PIPE,


                stdout=subprocess.DEVNULL,


                stderr=subprocess.DEVNULL,


                text=True,


                creationflags=0x08000000


            )


        except Exception as e:


            print(f"Failed to start notifier: {e}")


            self.proc = None





    def show_toast(self, title, msg, icon="info"):


        if not self.proc or self.proc.poll() is not None:


            self._start()





        if self.proc:


            try:


                import json


                data = json.dumps({"title": title, "msg": msg, "icon": icon})


                self.proc.stdin.write(data + "\n")


                self.proc.stdin.flush()


            except Exception as e:


                print(f"Failed to send toast: {e}")





_notifier_client = NotifierClient()


def show_toast(title, msg, icon="info"):


    _notifier_client.show_toast(title, msg, icon)


CONFIG_FILE = "config.json"


CACHE_FILE = "metadata_cache.json"

# Cache schema versions — bump to auto-invalidate incompatible old entries
METADATA_CACHE_VERSION = 2
GEMINI_CACHE_VERSION   = 2


ANILIST_IDENTITY_CACHE_KEY = "__anilist_identity_cache_v1__"


ANILIST_IDENTITY_VERSION = 1


ANILIST_IDENTITY_CONFIDENCE = 95


HISTORY_FILE = "history.json"


COVERS_DIR = "covers_cache"


DEFAULT_CLIENT_ID = "1465711556418474148"


CURRENT_VERSION = "5.3.2"


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


    "gemini_api_key": "",


    "discord_webhook_url": "",


    "scene_snapshots": False,


    "discord_widget_bot_token": "",


    "discord_widget_app_id": "",


    "discord_widget_user_id": "",


    "aniskip_auto_skip": False,


    "auto_score_popup": True


}





def query_gemini_title(filename, api_key):
    """Use Gemini REST API to get the exact official anime/media title and episode."""
    if not api_key: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    
    prompt = """
You are an expert media metadata resolver with internet knowledge.

Your task is to identify the ORIGINAL OFFICIAL TITLE of the media represented by the filename.

The filename may contain scene release names, fansub groups, resolutions, CRC hashes, roman numerals, and season/episode notation.
Your job is to reconstruct the OFFICIAL TITLE exactly as it appears on official sources (AniList, MyAnimeList, TMDB, IMDb).

Rules:
1. Preserve ALL official punctuation and subtitles (e.g. "Re:ZERO -Starting Life in Another World-").
2. NEVER REMOVE SEQUEL / INSTALLMENT MARKERS. Preserve sequel numbers, Roman numeral installment markers, and season-identifying words when they are part of the official title.
3. Do not reduce sequels to the franchise/base title. (e.g. "Overlord II" must remain "Overlord II", not "Overlord").
4. Treat Roman numerals like "I", "II", "III" as meaningful title components, especially in anime. DO NOT interpret them as episode numbers.
5. If a season or movie number is part of the title, preserve it in the "title" field, BUT ALSO populate the "base_title" and "season" fields.
6. Ignore completely: Resolution, Codec, Fansub/Release group, CRC, File extension.

Examples

Input:
Overlord II E10.mkv

Output:
{
  "title": "Overlord II",
  "base_title": "Overlord",
  "season": 2,
  "episode": 10,
  "media_type": "anime"
}

Input:
ReZERO - Starting Life in Another World Season 2 E08

Output:
{
  "title": "Re:ZERO -Starting Life in Another World- 2nd Season",
  "base_title": "Re:ZERO -Starting Life in Another World-",
  "season": 2,
  "episode": 8,
  "media_type": "anime"
}

Input:
SPY FAMILY S01E05

Output:
{
  "title": "SPY×FAMILY",
  "base_title": "SPY×FAMILY",
  "season": 1,
  "episode": 5,
  "media_type": "anime"
}

Input:
Fate Stay Night [Heaven's Feel] II. lost butterfly.mkv

Output:
{
  "title": "Fate/stay night [Heaven's Feel] II. lost butterfly",
  "base_title": "Fate/stay night",
  "season": null,
  "episode": null,
  "media_type": "movie"
}

Return ONLY valid JSON in this exact format:

{
  "title": "...",
  "base_title": "...",
  "season": <number or null>,
  "episode": <number or null>,
  "media_type": "anime|movie|tv_show|song|music|unknown"
}

Filename:
{filename}
"""
    prompt = prompt.replace('{filename}', filename)
    
    def _parse_response(text):
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        return parsed

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    try:
        import requests
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            text = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return _parse_response(text)
    except Exception as e:
        pass
    return None


def media_identity_to_display(identity):
    """Convert the structured title-parser result into the worker's display fields."""
    if not isinstance(identity, dict):
        return "", "", ""

    title = str(identity.get("title") or "").strip()
    media_type = str(identity.get("media_type") or "").strip()

    def _number(value):
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return ""

    season = _number(identity.get("season"))
    episode = _number(identity.get("episode"))
    if season and episode:
        episode_str = f"Season {season} Episode {episode}"
    elif episode:
        episode_str = f"Episode {episode}"
    elif season:
        episode_str = f"Season {season}"
    else:
        episode_str = ""

    return title, episode_str, media_type


def clean_title(title):
    """Parse a raw filename into structured media identity data."""
    import re
    import guessit
    title = str(title or "")
    title = re.sub(r'^\d+[\.\-]\s+', '', title)
    title = re.sub(r'\.(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', title, flags=re.I).strip()
    title = re.sub(r'\s+(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', title, flags=re.I).strip()
    
    result = {
        "title": title,
        "base_title": "",
        "season": None,
        "episode": None,
        "media_type": ""
    }

    loose_ep = re.search(r"(?<!\d)([A-Za-z][\w\s\.'\.\-:&!,;\(\)\[\]]+?)[\s\._]+(?:Episode|Ep|E)?\s*(\d{1,4})(?:v\d+)?\s*$", title, re.I)
    explicit_ep = re.search(r'\b(?:Episode|Ep|E)\s*\d{1,4}\s*$', title, re.I)
    
    raw_title_for_guessit = title
    if loose_ep:
        ep_num = int(loose_ep.group(2))
        if explicit_ep or not (1900 <= ep_num <= 2099):
            raw_title = re.sub(r'[\._ ]+', ' ', loose_ep.group(1)).strip()
            raw_title = re.sub(r'[\s\-]+$', '', raw_title).strip()
            result["episode"] = ep_num
            raw_title_for_guessit = raw_title

    try:
        guessed = guessit.guessit(raw_title_for_guessit)
        cleaned = guessed.get('title', raw_title_for_guessit)
        media_type = guessed.get('type', '')

        if media_type == 'movie':
            year = guessed.get('year')
            if year:
                cleaned = f"{cleaned} ({year})"
        
        season = guessed.get('season')
        episode = guessed.get('episode')
        
        if isinstance(season, list): season = season[0]
        if isinstance(episode, list): episode = episode[0]
        
        result["title"] = cleaned
        if season: result["season"] = season
        
        if episode is not None:
            if result["episode"] is not None:
                if str(season) + str(episode) == str(result["episode"]):
                    result["season"] = None
                else:
                    result["episode"] = episode
            else:
                result["episode"] = episode
                
        result["media_type"] = media_type if media_type else ""
    except Exception as e:
        pass

    return result















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








def _legacy_config_path():
    application_path = (
        os.path.dirname(sys.executable)
        if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__))
    )
    return os.path.join(application_path, CONFIG_FILE)


def _persistent_config_path():
    """Keep OAuth credentials outside the replaceable application directory."""
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(local_app_data, "VLC RPC", CONFIG_FILE)


def _read_config_file(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
        if not isinstance(config, dict):
            return None
        merged = DEFAULT_CONFIG.copy()
        merged.update(config)
        return merged
    except Exception:
        return None


def load_config():
    persistent_path = _persistent_config_path()
    config = _read_config_file(persistent_path)
    if config is not None:
        return config

    # Upgrade installations that stored config.json beside VLC RPC.exe. This
    # runs once, before an update can replace that directory and lose OAuth.
    legacy_path = _legacy_config_path()
    config = _read_config_file(legacy_path)
    if config is not None:
        save_config(config)
        return config
    return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        config_path = _persistent_config_path()
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        tmp_path = config_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as config_file:
            json.dump(config, config_file, indent=4)
            config_file.flush()
            os.fsync(config_file.fileno())
        os.replace(tmp_path, config_path)
    except Exception:
        pass









import queue
from pypresence import Presence

class DiscordManager(threading.Thread):
    def __init__(self, backend_ref, initial_client_id):
        super().__init__(daemon=True)
        self.backend_ref = backend_ref
        self.cmd_queue = queue.Queue()
        self.rpc = None
        self.current_client_id = None
        self.current_generation = -1
        self.current_kwargs = None
        self.initial_client_id = initial_client_id
        
        self.rpc_backoff = 1
        self.rpc_reconnect_at = 0.0
        self.state = "DISCONNECTED"
        self._stop_event = threading.Event()
        self.last_update_time = 0

    def submit_activity(self, generation, client_id, kwargs):
        self.cmd_queue.put({"type": "update", "generation": generation, "client_id": client_id, "kwargs": kwargs})
        
    def clear_activity(self, generation):
        self.cmd_queue.put({"type": "clear", "generation": generation})
        
    def stop(self):
        self._stop_event.set()
        self.cmd_queue.put({"type": "stop"})
        
    def set_state(self, new_state, message):
        self.state = new_state
        self.backend_ref.state_data["rpc_connected"] = (new_state == "CONNECTED")
        health_status = "HEALTHY" if new_state == "CONNECTED" else ("RECONNECTING" if new_state in ("CONNECTING", "RECONNECTING") else "DISCONNECTED")
        self.backend_ref.state_data.setdefault("health", {})["discord"] = health_status
        if message:
            self.backend_ref.state_data["status_message"] = message
            if "error" in message.lower() or "dropped" in message.lower():
                self.backend_ref.log(f"[DISCORD] {message}")
            elif "Connecting" in message or "Shutting" in message or "Shutdown" in message or "Closing" in message:
                self.backend_ref.log(f"[DISCORD] {message}")
            else:
                # Usually "Connected to Discord."
                self.backend_ref.log(f"[RECOVERY] Discord reconnect successful: {message}")

    def truncate_str(self, val, limit=120):
        if isinstance(val, str) and len(val) > limit:
            return val[:limit-3] + "..."
        return val

    def process_kwargs(self, kwargs):
        if not kwargs: return kwargs
        ret = kwargs.copy()
        if "details" in ret: ret["details"] = self.truncate_str(ret["details"])
        if "state" in ret: ret["state"] = self.truncate_str(ret["state"])
        if "large_text" in ret: ret["large_text"] = self.truncate_str(ret["large_text"])
        return ret
        
    def _is_significant_change(self, old, new):
        if not old: return True
        if set(old.keys()) != set(new.keys()): return True
        for k, v in new.items():
            if k in ('start', 'end') and isinstance(v, (int, float)):
                old_v = old.get(k)
                if not isinstance(old_v, (int, float)) or abs(v - old_v) > 3:
                    return True
            elif old.get(k) != v:
                return True
        return False

    def run(self):
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        
        self.set_state("CONNECTING", "Starting Discord manager...")
        desired_client_id = self.initial_client_id
        
        while not self._stop_event.is_set():
            try:
                cmd = self.cmd_queue.get(timeout=1.0)
                if cmd["type"] == "stop":
                    break
                elif cmd["type"] == "clear":
                    if cmd["generation"] >= self.current_generation:
                        self.current_generation = cmd["generation"]
                        self.current_kwargs = None
                elif cmd["type"] == "update":
                    if cmd["generation"] >= self.current_generation:
                        self.current_generation = cmd["generation"]
                        desired_client_id = cmd["client_id"]
                        self.current_kwargs = cmd["kwargs"]
            except queue.Empty:
                pass

            if self._stop_event.is_set():
                break

            # Handle Client ID changes
            if self.rpc and desired_client_id and self.current_client_id != desired_client_id:
                try: self.rpc.close()
                except Exception: pass
                self.rpc = None
                self.current_client_id = None
                self.set_state("DISCONNECTED", f"Closing Discord RPC (Client ID changed to {desired_client_id})")

            # Connect / Reconnect
            if not self.rpc and desired_client_id and time.time() >= self.rpc_reconnect_at:
                self.set_state("CONNECTING", f"Connecting to Discord RPC (Client ID: {desired_client_id})...")
                try:
                    self.rpc = Presence(desired_client_id)
                    self.rpc.connect()
                    self.current_client_id = desired_client_id
                    self.set_state("CONNECTED", "Connected to Discord.")
                    self.rpc_backoff = 1
                    self.rpc_reconnect_at = 0.0
                    self.last_update_time = 0
                    self._last_published_kwargs = None
                except Exception as e:
                    self.rpc = None
                    self.current_client_id = None
                    self.set_state("RECONNECTING", f"Discord not found or error ({e}) \u2014 retrying...")
                    self.rpc_reconnect_at = time.time() + self.rpc_backoff
                    self.rpc_backoff = min(self.rpc_backoff * 2, 30)

            # Publish
            if self.rpc and self.state == "CONNECTED":
                if not self.current_kwargs:
                    if getattr(self, "_last_published_kwargs", None) is not None:
                        try:
                            self.rpc.clear()
                            self._last_published_kwargs = None
                            self.backend_ref.log("[DISCORD] Activity cleared")
                        except Exception:
                            pass
                else:
                    processed = self.process_kwargs(self.current_kwargs)
                    last_published = getattr(self, "_last_published_kwargs", {})
                    if self._is_significant_change(last_published, processed):
                        now = time.time()
                        if now - self.last_update_time >= 5:
                            try:
                                self.rpc.update(**processed)
                                self._last_published_kwargs = processed.copy()
                                self.last_update_time = now
                            except Exception as e:
                                self.backend_ref.log(f"[DISCORD] Update error: {e}")
                                try: self.rpc.close()
                                except Exception: pass
                                self.rpc = None
                                self.current_client_id = None
                                self.set_state("RECONNECTING", "Connection dropped during update \u2014 scheduling reconnect.")
                                self.rpc_reconnect_at = time.time() + self.rpc_backoff
                                self.rpc_backoff = min(self.rpc_backoff * 2, 30)

        # Shutdown
        self.set_state("STOPPING", "Shutting down Discord manager...")
        if self.rpc:
            try: self.rpc.clear()
            except Exception: pass
            try: self.rpc.close()
            except Exception: pass
        self.set_state("DISCONNECTED", "Shutdown complete.")



class RPCBackend:


    def __init__(self):


        self.config = DEFAULT_CONFIG.copy()


        self.config.update(load_config())


        self.metadata_cache = {}


        self.gemini_fail_times = {}  # tracks last failure time per filename for retry logic
        self._metadata_neg_cache = {} # maps cache_key -> (fail_time, fail_count)
        self._anilist_fail_count = 0
        self._anilist_backoff_until = 0.0


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


            "local_arturl": "",


            "_last_art_key": "",


            "_last_art_uri": "",


            "exit_flag": False,


            "update_available": False,


            "update_version": "",


            "update_download_url": "",


            "update_changelog": "",


            "scene_snapshot_url": "",


            "anilist_score_format": "POINT_100",


            "anilist_identity": None,


            "anilist_identity_state": "UNKNOWN",
            "watch_mode": "NORMAL",
            "rewatch_number": 0,
            "possible_rewatch": False,
            "rewatch_starting": False,
            # Generation stamp: rewatch state is only valid for the generation
            # in which it was written. Stale writes from async threads are ignored.
            "_rewatch_generation": -1,
            "health": {
                "vlc": "UNKNOWN",
                "discord": "DISCONNECTED",
                "anilist": "UNKNOWN",
                "gemini": "UNKNOWN",
                "metadata": "UNKNOWN",
                "cache": "HEALTHY",
                "ffmpeg": "UNKNOWN"
            }
        }


        self.force_update_flag = False


        self.scrobbled_episodes = set()


        self.current_anilist_identity = None


        self.anilist_identity_cache = {}


        self._anilist_identity_resolving = set()


        self._anilist_identity_lock = threading.Lock()


        self._anilist_media_list_refreshing = set()


        self._rewatch_start_lock = threading.Lock()

        self._metadata_cache_lock = threading.Lock()
        self._gemini_cache_lock = threading.Lock()


        self.anilist_username_cache = None   # None = not fetched yet; False = fetch failed


        self._last_snapshot_time = 0         # epoch time of last scene snapshot


        self.last_sync_time = 0


        self.window = None


        self.stop_event = threading.Event()


        self.current_watch_duration = 0


        self.anilist_logs = []


        self.history = self.load_history()


        self.setup_database()


        self.aniskip_cache = {}  # cache: (anilist_id, episode) -> {op_start, op_end, ed_start, ed_end}


        self.aniskip_notified = set()  # tracks already-notified (title, ep, section)


        self.scored_episodes = set()  # tracks already-scored (title, ep)


        self.metadata_cache = self.load_metadata_cache()


        cached_identities = self.metadata_cache.get(ANILIST_IDENTITY_CACHE_KEY, {})


        if isinstance(cached_identities, dict):


            self.anilist_identity_cache = cached_identities


        


        # Load gemini cache


        self.gemini_cache_file = 'gemini_cache.json'


        self.gemini_cache = {}

        # Resolve cache path relative to exe/script, same as metadata cache
        if getattr(sys, 'frozen', False):
            _gcache_base = os.path.dirname(sys.executable)
        else:
            _gcache_base = os.path.dirname(os.path.abspath(__file__))
        self.gemini_cache_file = os.path.join(_gcache_base, self.gemini_cache_file)

        # Hardened Gemini cache load -- validate schema, backup on corruption
        try:
            if os.path.exists(self.gemini_cache_file):
                try:
                    raw_gc = open(self.gemini_cache_file, 'r', encoding='utf-8').read().strip()
                except Exception:
                    raw_gc = ''
                if raw_gc:
                    try:
                        raw_dict = json.loads(raw_gc)
                    except Exception:
                        print('[RECOVERY] Gemini cache repaired -- JSON parse failed; backing up bad file.')
                        if hasattr(self, "state_data") and "health" in self.state_data: self.state_data["health"]["cache"] = "REPAIRED"
                        try:
                            import shutil
                            shutil.copy2(self.gemini_cache_file, self.gemini_cache_file + '.bak')
                        except Exception:
                            pass
                        raw_dict = {}
                    if not isinstance(raw_dict, dict):
                        raw_dict = {}
                    cleaned_gc = {}
                    for k, v in raw_dict.items():
                        if v is None or v == 'pending':
                            continue
                        if isinstance(v, list) and len(v) >= 2:
                            cleaned_gc[k] = tuple(v)
                        elif isinstance(v, tuple) and len(v) >= 2:
                            cleaned_gc[k] = v
                    self.gemini_cache = cleaned_gc
        except Exception as ex:
            print('[GEMINI CACHE] Load error:', ex)
            self.gemini_cache = {}





        self.media_generation = 0
        self.worker_thread = threading.Thread(target=self.rpc_worker, daemon=True)


        self.worker_thread.start()
        initial_client_id = self.config.get("client_id", "").strip() or DEFAULT_CLIENT_ID
        self.discord_manager = DiscordManager(self, initial_client_id)
        self.discord_manager.start()



        


        # Trigger an initial widget sync on startup


        threading.Thread(target=self.force_sync_widget, daemon=True).start()


        threading.Thread(target=self.force_sync_widget_v2, daemon=True).start()





    def log(self, msg, toast_title=None, toast_icon="info"):


        timestamp = datetime.datetime.now().strftime("%H:%M:%S")


        formatted = f"[{timestamp}] {msg}"


        if self.window:


            try:


                self.window.evaluate_js(f"if(window.addLog) window.addLog({json.dumps(formatted)});")


            except Exception:


                pass


        if toast_title:


            show_toast(toast_title, msg, icon=toast_icon)





    def load_history(self):


        if getattr(sys, 'frozen', False):


            application_path = os.path.dirname(sys.executable)


        else:


            application_path = os.path.dirname(os.path.abspath(__file__))


        history_path = os.path.join(application_path, HISTORY_FILE)


        


        if not os.path.exists(history_path):


            return []


        try:


            with open(history_path, "r") as f:


                return json.load(f)


        except Exception:


            return []





    def save_history(self):


        if getattr(sys, 'frozen', False):


            application_path = os.path.dirname(sys.executable)


        else:


            application_path = os.path.dirname(os.path.abspath(__file__))


        history_path = os.path.join(application_path, HISTORY_FILE)


        try:
            tmp_path = history_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, history_path)
        except Exception:
            pass





    def anilist_log(self, msg):


        """Append timestamped entry to in-app AniList log and Discord webhook."""


        import datetime


        entry = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"


        self.anilist_logs.append(entry)


        if len(self.anilist_logs) > 200:


            self.anilist_logs = self.anilist_logs[-200:]


        try:


            pass


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


        webhook_url = self.config.get("discord_webhook_url", "").strip()


        if not webhook_url:


            return


            


        try:


            payload = {"content": f"**[VLC RPC Tracker]** {message}"}


            response = requests.post(webhook_url, json=payload, timeout=5)


            if response.status_code not in (204, 200, 201):


                pass


        except Exception as e:


            pass


            # swallow to avoid breaking main flow


            pass





    @staticmethod
    def _normalize_anilist_title(value):
        value = unicodedata.normalize("NFKD", str(value or ""))
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


    @staticmethod
    def _anilist_season_hint(title, episode_str=""):
        source = f"{title or ''} {episode_str or ''}".lower()
        patterns = (
            r"\bseason\s*(\d{1,2})\b",
            r"\bs(\d{1,2})e?\d*\b",
            r"\b(\d{1,2})(?:st|nd|rd|th)\s+season\b",
            r"\b(?:part|cour)\s*(\d{1,2})\b",
        )
        for pattern in patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 1


    def _anilist_identity_key(self, title, episode_str=""):
        normalized = self._normalize_anilist_title(title)
        base = re.sub(
            r"\b(?:season\s*\d+|\d+(?:st|nd|rd|th)\s+season|part\s*\d+|cour\s*\d+)\b",
            " ",
            normalized,
        )
        base = re.sub(r"\s+", " ", base).strip()
        season = self._anilist_season_hint(title, episode_str)
        return f"{base}|season:{season}", base, season


    def _anilist_candidate_score(self, requested_title, episode_str, candidate):
        """Return a conservative score for one AniList candidate.

        A title similarity alone is never sufficient for a later season.  This
        deliberately prefers an unresolved sync over a potentially wrong ID.
        """
        requested = self._normalize_anilist_title(requested_title)
        _, requested_base, requested_season = self._anilist_identity_key(
            requested_title, episode_str
        )
        if not requested:
            return 0, "empty requested title"

        title_data = candidate.get("title") or {}
        variants = [
            title_data.get("english"),
            title_data.get("romaji"),
            title_data.get("native"),
            *(candidate.get("synonyms") or []),
        ]
        variants = [self._normalize_anilist_title(item) for item in variants if item]
        if not variants:
            return 0, "candidate has no titles"

        score = 0
        reason = "titles differ"
        for variant in variants:
            if variant == requested:
                score = max(score, 100)
                reason = "exact title"
            else:
                _, variant_base, _ = self._anilist_identity_key(variant)
                if requested_base and variant_base == requested_base:
                    score = max(score, 88)
                    reason = "exact base title"
                # AniList commonly labels a sequel as "Title 2", while local
                # files use "Title Season 2". Treat that as exact only when
                # both the base title and the explicit season number agree.
                numeric_sequel = re.fullmatch(r"(.+?)\s+(\d{1,2})", variant)
                if requested_season > 1 and numeric_sequel:
                    sequel_base = numeric_sequel.group(1).strip()
                    sequel_number = int(numeric_sequel.group(2))
                    if sequel_base == requested_base and sequel_number == requested_season:
                        score = max(score, 100)
                        reason = "exact base title with matching numeric sequel"
                elif len(requested) >= 8 and len(variant) >= 8:
                    ratio = SequenceMatcher(None, requested, variant).ratio()
                    if ratio >= 0.97:
                        score = max(score, 84)
                        reason = "near-exact title"

        candidate_season = max(
            self._anilist_season_hint(item) for item in variants
        )
        for variant in variants:
            numeric_sequel = re.fullmatch(r"(.+?)\s+(\d{1,2})", variant)
            if (
                requested_season > 1
                and numeric_sequel
                and numeric_sequel.group(1).strip() == requested_base
            ):
                candidate_season = max(candidate_season, int(numeric_sequel.group(2)))
        if requested_season > 1:
            if candidate_season == requested_season:
                score += 12
                reason += ", season matches"
            elif candidate_season > 1:
                score -= 75
                reason += ", different season"
            else:
                score -= 50
                reason += ", candidate season is unspecified"
        elif candidate_season > 1:
            score -= 75
            reason += ", candidate is a later season"

        if candidate.get("type") != "ANIME":
            return 0, "not an anime entry"
        if candidate.get("format") == "MOVIE" and "episode" in str(episode_str).lower():
            score -= 60
            reason += ", movie/episode mismatch"
        return max(0, min(score, 100)), reason


    def _apply_anilist_identity(self, identity, launch_generation=None):
        # Generation guard: only the async resolver passes launch_generation.
        # Synchronous (poll-loop) callers always apply immediately.
        if launch_generation is not None and self.media_generation != launch_generation:
            self.log(
                f"[STATE] Discarded stale identity apply from generation {launch_generation} "
                f"(current={self.media_generation})"
            )
            return
        self.current_anilist_identity = identity
        self.state_data["anilist_identity"] = identity.copy()
        self.state_data["anilist_identity_state"] = identity.get("state", "UNKNOWN")


        # Retain the full provider metadata object. Only enrich its canonical ID
        # after identity validation; covers, ratings, genres and descriptions are
        # intentionally left untouched.
        metadata = self.state_data.get("metadata")
        if (
            isinstance(metadata, dict)
            and identity.get("state") == "SYNCABLE"
            and identity.get("validated")
        ):
            metadata["anilistId"] = identity["anilist_id"]
            if identity.get("episodes"):
                metadata["total_episodes"] = identity["episodes"]

        if (
            identity.get("state") == "SYNCABLE"
            and identity.get("validated")
            and identity.get("anilist_id")
        ):
            self.refresh_anilist_media_list(identity["anilist_id"])


    def _get_anilist_media_list(self, anilist_id):
        """Read the authenticated user's entry for one already-verified media ID."""
        token = self.config.get("anilist_token", "").strip()
        if not token:
            raise RuntimeError("AniList authentication is required")

        username = getattr(self, "anilist_username_cache", None)
        if not username:
            try:
                r = requests.post(
                    "https://graphql.anilist.co",
                    json={"query": "query { Viewer { name } }"},
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    timeout=5
                )
                if r.status_code == 200:
                    username = (r.json().get("data") or {}).get("Viewer", {}).get("name")
                    if username:
                        self.anilist_username_cache = username
            except Exception:
                pass

        if username:
            query = """
            query ($mediaId: Int, $userName: String) {
              MediaList(mediaId: $mediaId, userName: $userName) {
                id status progress repeat
                media { id episodes }
              }
            }
            """
            variables = {"mediaId": anilist_id, "userName": username}
        else:
            query = """
            query ($mediaId: Int) {
              MediaList(mediaId: $mediaId) {
                id status progress repeat
                media { id episodes }
              }
            }
            """
            variables = {"mediaId": anilist_id}

        response = requests.post(
            "https://graphql.anilist.co",
            json={"query": query, "variables": variables},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=10,
        )
        if response.status_code == 401:
            self.config["anilist_token"] = ""
            save_config(self.config)
            raise RuntimeError("AniList authentication expired")
        payload = response.json()
        errors = payload.get("errors") or []
        if response.status_code != 200 or errors:
            reason = errors[0].get("message", f"AniList HTTP {response.status_code}") if errors else f"AniList HTTP {response.status_code}"
            raise RuntimeError(reason)

        media_list = (payload.get("data") or {}).get("MediaList")
        if media_list:
            media_id = ((media_list.get("media") or {}).get("id"))
            if media_id != anilist_id:
                raise RuntimeError("Media ID mismatch")
        return media_list


    def _apply_anilist_media_list(self, anilist_id, media_list, launch_generation=None):
        """Apply a fresh MediaList response only if its ID and generation are still current."""
        current = self.current_anilist_identity or {}
        if current.get("anilist_id") != anilist_id:
            return False
        # Generation guard: if media changed since this refresh was launched, discard
        if launch_generation is not None and self.media_generation != launch_generation:
            self.log(
                f"[STATE] Discarded stale MediaList apply for ID {anilist_id} "
                f"(gen {launch_generation} -> {self.media_generation})"
            )
            return False

        trigger_rewatch_popup = False
        with self._anilist_identity_lock:
            current["media_list"] = media_list
            state_identity = self.state_data.get("anilist_identity")
            if isinstance(state_identity, dict):
                state_identity["media_list"] = media_list

            status = (media_list or {}).get("status")
            if status == "REPEATING":
                self.state_data["watch_mode"] = "REWATCH"
                self.state_data["rewatch_number"] = (media_list or {}).get("repeat") or 1
                self.state_data["possible_rewatch"] = False
                self.state_data["_rewatch_generation"] = self.media_generation
                self.log(f"[REWATCH] Mode=REWATCH (repeat #{self.state_data['rewatch_number']}) "
                         f"for session {self.media_generation}")
            elif status == "COMPLETED":
                # User is watching an anime they already completed — possible rewatch
                self.state_data["watch_mode"] = "NORMAL"
                self.state_data["rewatch_number"] = 0
                self.state_data["_rewatch_generation"] = self.media_generation
                if not self.state_data.get("possible_rewatch"):
                    self.state_data["possible_rewatch"] = True
                    trigger_rewatch_popup = True
            else:
                self.state_data["watch_mode"] = "NORMAL"
                self.state_data["rewatch_number"] = 0
                self.state_data["possible_rewatch"] = False
                self.state_data["_rewatch_generation"] = self.media_generation

        if trigger_rewatch_popup:
            self._show_rewatch_popup(anilist_id, media_list)
        return True


    def _show_rewatch_popup(self, anilist_id, media_list):
        """Show a rewatch confirmation popup via the notifier subprocess."""
        identity = self.current_anilist_identity or {}
        title = identity.get("title") or identity.get("source_title") or ""
        repeat = (media_list or {}).get("repeat") or 0
        token = self.config.get("anilist_token", "").strip()

        # Deduplicate: only prompt once per AniList ID per session
        rewatch_key = (anilist_id, "rewatch_prompt")
        if rewatch_key in self.scored_episodes:
            return
        self.scored_episodes.add(rewatch_key)

        if not token:
            self.anilist_log("[AniList] Rewatch popup skipped: no AniList token.")
            return

        if _notifier_client.proc:
            try:
                import json as _json
                data = _json.dumps({
                    "type": "rewatch_popup",
                    "title": title,
                    "media_id": anilist_id,
                    "current_repeat": repeat,
                    "token": token,
                })
                _notifier_client.proc.stdin.write(data + "\n")
                _notifier_client.proc.stdin.flush()
                self.anilist_log(f"[AniList] Rewatch popup triggered for '{title}'.")
            except Exception as e:
                self.log(f"Failed to trigger rewatch popup: {e}")


    def _check_rewatch_signals(self):
        """Check for signal files written by the notifier after a rewatch is started."""
        try:
            signal_dir = os.path.join(application_path, "rewatch_signals")
            if not os.path.isdir(signal_dir):
                return
            for fname in os.listdir(signal_dir):
                if not fname.endswith(".signal"):
                    continue
                fpath = os.path.join(signal_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as sf:
                        import json as _json
                        sig = _json.load(sf)
                    os.remove(fpath)
                    media_id = sig.get("media_id")
                    new_repeat = sig.get("repeat")
                    if media_id:
                        # Guard: only process signal if it matches the currently playing media
                        current_id = (self.current_anilist_identity or {}).get("anilist_id")
                        if media_id != current_id:
                            self.log(
                                f"[REWATCH] Signal for ID {media_id} discarded "
                                f"— current media is ID {current_id}"
                            )
                        else:
                            self.anilist_log(
                                f"[AniList] Rewatch signal received: ID {media_id}, repeat #{new_repeat}."
                            )
                            # Reset possible_rewatch so the popup doesn't re-trigger
                            self.state_data["possible_rewatch"] = False
                            # Refresh the MediaList to pick up the new REPEATING status
                            self.refresh_anilist_media_list(media_id)
                except Exception as exc:
                    self.log(f"[Rewatch] Failed to process signal {fname}: {exc}")
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass
        except Exception:
            pass


    def _refresh_anilist_media_list_bg(self, anilist_id, launch_generation=None):
        try:
            media_list = self._get_anilist_media_list(anilist_id)
            if self._apply_anilist_media_list(anilist_id, media_list, launch_generation):
                if self._anilist_fail_count > 0:
                    self._set_health("anilist", "HEALTHY", "AniList request retried successfully")
                self._anilist_fail_count = 0
                self._anilist_backoff_until = 0.0
                status = (media_list or {}).get("status") or "MISSING"
                repeat = (media_list or {}).get("repeat") or 0
                self.anilist_log(
                    f"[AniList] MediaList ID {anilist_id}: status={status}, repeat={repeat}"
                )
        except Exception as exc:
            self._anilist_fail_count += 1
            backoff = min(30 * (2 ** self._anilist_fail_count), 3600)
            self._anilist_backoff_until = time.time() + backoff
            self._set_health("anilist", "DEGRADED", f"AniList refresh failed: {exc}")
        finally:
            with self._anilist_identity_lock:
                self._anilist_media_list_refreshing.discard(anilist_id)


    def refresh_anilist_media_list(self, anilist_id=None):
        """Schedule one MediaList refresh; never run it from the VLC poll loop."""
        anilist_id = anilist_id or (self.current_anilist_identity or {}).get("anilist_id")
        if not anilist_id or not self.config.get("anilist_token", "").strip():
            return False
        # Capture generation NOW so the background thread can reject stale applies
        launch_generation = self.media_generation
        with self._anilist_identity_lock:
            if anilist_id in self._anilist_media_list_refreshing:
                return False
            self._anilist_media_list_refreshing.add(anilist_id)
        threading.Thread(
            target=self._refresh_anilist_media_list_bg,
            args=(anilist_id, launch_generation),
            daemon=True,
        ).start()
        return True


    def _start_anilist_rewatch(self):
        """Start exactly one native AniList rewatch after a fresh entry check."""
        if not self._rewatch_start_lock.acquire(blocking=False):
            self.anilist_log("[AniList] Rewatch start already in progress.")
            return False

        # Capture generation at entry. If media changes before we finish,
        # we discard the result rather than writing REWATCH state to the new title.
        entry_gen = self.media_generation
        self.state_data["rewatch_starting"] = True
        try:
            identity = self.current_anilist_identity or {}
            if (
                identity.get("state") != "SYNCABLE"
                or not identity.get("validated")
                or not identity.get("anilist_id")
            ):
                self.anilist_log("[AniList] Rewatch aborted: identity is not verified.")
                return False
            if not self.config.get("anilist_token", "").strip():
                self.anilist_log("[AniList] Rewatch aborted: AniList authentication is required.")
                return False

            media_id = identity["anilist_id"]
            media_list = self._get_anilist_media_list(media_id)
            if not media_list:
                self.anilist_log("[AniList] Rewatch aborted: no MediaList entry exists.")
                return False
            if ((media_list.get("media") or {}).get("id")) != media_id:
                self.anilist_log("[AniList] Rewatch aborted: Media ID mismatch.")
                return False
            if media_list.get("status") == "REPEATING":
                if self.media_generation != entry_gen:
                    self.anilist_log("[AniList] Rewatch aborted: media changed during fetch.")
                    return False
                self._apply_anilist_media_list(media_id, media_list, entry_gen)
                self.anilist_log(
                    f"[AniList] Already rewatching #{media_list.get('repeat') or 1}; no repeat increment."
                )
                return True
            if media_list.get("status") != "COMPLETED":
                self.anilist_log(
                    f"[AniList] Rewatch aborted: MediaList status is {media_list.get('status') or 'MISSING'}."
                )
                return False

            target_repeat = (media_list.get("repeat") or 0) + 1
            self.anilist_log(
                f"[AniList] Starting rewatch for ID {media_id}: repeat {target_repeat}."
            )
            mutation = """
            mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus, $repeat: Int) {
              SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: $status, repeat: $repeat) {
                id status progress repeat
                media { id episodes }
              }
            }
            """
            response = requests.post(
                "https://graphql.anilist.co",
                json={"query": mutation, "variables": {
                    "mediaId": media_id,
                    "progress": 0,
                    "status": "REPEATING",
                    "repeat": target_repeat,
                }},
                headers={
                    "Authorization": f"Bearer {self.config['anilist_token'].strip()}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=10,
            )
            payload = response.json()
            entry = ((payload.get("data") or {}).get("SaveMediaListEntry") or {})
            if (
                response.status_code == 200
                and entry.get("status") == "REPEATING"
                and entry.get("repeat") == target_repeat
                and ((entry.get("media") or {}).get("id")) == media_id
            ):
                if self.media_generation != entry_gen:
                    self.anilist_log(
                        "[AniList] Rewatch mutation succeeded but media changed — state not applied."
                    )
                    return False
                self._apply_anilist_media_list(media_id, entry, entry_gen)
                self.anilist_log(
                    f"[AniList] Rewatch #{target_repeat} started successfully for ID {media_id}."
                )
                return True

            errors = payload.get("errors") or []
            reason = errors[0].get("message", "AniList mutation failed") if errors else "AniList mutation failed"
            self.anilist_log(f"[AniList] Rewatch start failed: {reason}")
            return False
        except Exception as exc:
            # A timeout can occur after AniList accepted the mutation. Re-read
            # the authoritative entry before reporting failure; never retry an
            # increment blindly.
            try:
                identity = self.current_anilist_identity or {}
                media_id = identity.get("anilist_id")
                media_list = self._get_anilist_media_list(media_id) if media_id else None
                if media_list and media_list.get("status") == "REPEATING":
                    if self.media_generation == entry_gen:
                        self._apply_anilist_media_list(media_id, media_list, entry_gen)
                        self.anilist_log(
                            f"[AniList] Rewatch recovered from ambiguous response: #{media_list.get('repeat') or 1}."
                        )
                        return True
            except Exception:
                pass
            self.anilist_log(f"[AniList] Rewatch start failed: {exc}")
            return False
        finally:
            self.state_data["rewatch_starting"] = False
            self._rewatch_start_lock.release()


    def start_anilist_rewatch(self):
        """Queue a rewatch mutation without blocking the pywebview UI thread."""
        if self.state_data.get("rewatch_starting"):
            return False
        threading.Thread(target=self._start_anilist_rewatch, daemon=True).start()
        return True


    def _legacy_metadata_identity(self, identity_key, title):
        """Lazily upgrade only exact-title legacy metadata records.

        Older cache entries lack a confidence marker.  An ID is adopted only if
        its stored official title is an exact normalized match, never by cache
        key, containment, or result ordering.
        """
        normalized = self._normalize_anilist_title(title)
        for metadata in self.metadata_cache.values():
            if not isinstance(metadata, dict) or not metadata.get("anilistId"):
                continue
            official = self._normalize_anilist_title(
                metadata.get("official_title") or metadata.get("title")
            )
            if not official or official != normalized:
                continue
            identity = {
                "anilist_id": metadata["anilistId"],
                "title": metadata.get("official_title") or title,
                "title_romaji": metadata.get("title_romaji", ""),
                "title_english": metadata.get("title_english", ""),
                "title_native": metadata.get("title_native", ""),
                "format": metadata.get("format", ""),
                "season": metadata.get("season"),
                "season_year": metadata.get("season_year"),
                "episodes": metadata.get("total_episodes") or metadata.get("episodes"),
                "media_type": "ANIME",
                "source_key": identity_key,
                "source_title": title,
                "normalized_title": normalized,
                "confidence": ANILIST_IDENTITY_CONFIDENCE / 100,
                "resolved_at": datetime.datetime.utcnow().isoformat() + "Z",
                "identity_version": ANILIST_IDENTITY_VERSION,
                "state": "SYNCABLE",
                "validated": True,
            }
            self.anilist_identity_cache[identity_key] = identity.copy()
            self.save_metadata_cache()
            self.anilist_log(
                f"[AniList] Upgraded exact legacy metadata to ID {identity['anilist_id']}."
            )
            return identity
        return None


    def _resolve_anilist_identity(self, identity_key, title, episode_str, launch_generation=None):
        """Resolve one series identity once; this never runs from a sync call."""
        if time.time() < self._anilist_backoff_until:
            self.anilist_log("[AniList] Circuit open — backing off (resolve).")
            with self._anilist_identity_lock:
                self._anilist_identity_resolving.discard(identity_key)
            return
        try:
            self.anilist_log(f"[AniList] Resolving identity: {title}")
            query = """
            query ($search: String) {
              Page(page: 1, perPage: 10) {
                media(search: $search, type: ANIME) {
                  id idMal type format status season seasonYear episodes duration
                  title { romaji english native }
                  synonyms
                  relations { edges { relationType node { id type format season seasonYear episodes title { romaji english native } } } }
                  coverImage { extraLarge large medium }
                  bannerImage description(asHtml: false) genres averageScore meanScore
                  startDate { year month day } endDate { year month day } siteUrl
                }
              }
            }
            """
            response = requests.post(
                "https://graphql.anilist.co",
                json={"query": query, "variables": {"search": title}},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if response.status_code != 200:
                raise RuntimeError(f"AniList HTTP {response.status_code}")
            payload = response.json()
            if payload.get("errors"):
                raise RuntimeError(payload["errors"][0].get("message", "AniList query failed"))
            candidates = ((payload.get("data") or {}).get("Page") or {}).get("media") or []
            scored = []
            for candidate in candidates:
                score, reason = self._anilist_candidate_score(title, episode_str, candidate)
                if score:
                    scored.append((score, reason, candidate))
            scored.sort(key=lambda item: item[0], reverse=True)

            if not scored or scored[0][0] < ANILIST_IDENTITY_CONFIDENCE:
                identity = {
                    "source_key": identity_key,
                    "source_title": title,
                    "normalized_title": self._normalize_anilist_title(title),
                    "state": "UNRESOLVED",
                    "validated": False,
                    "confidence": scored[0][0] / 100 if scored else 0.0,
                    "identity_version": ANILIST_IDENTITY_VERSION,
                }
                self.anilist_log("[AniList] Identity unresolved; sync skipped.")
            elif len(scored) > 1 and scored[0][0] - scored[1][0] < 5:
                identity = {
                    "source_key": identity_key,
                    "source_title": title,
                    "normalized_title": self._normalize_anilist_title(title),
                    "state": "AMBIGUOUS",
                    "validated": False,
                    "confidence": scored[0][0] / 100,
                    "identity_version": ANILIST_IDENTITY_VERSION,
                }
                self.anilist_log("[AniList] Identity ambiguous; AniList progress not modified.")
            else:
                score, reason, media = scored[0]
                titles = media.get("title") or {}
                identity = {
                    "anilist_id": media.get("id"),
                    "title": titles.get("english") or titles.get("romaji") or title,
                    "title_romaji": titles.get("romaji") or "",
                    "title_english": titles.get("english") or "",
                    "title_native": titles.get("native") or "",
                    "format": media.get("format") or "",
                    "season": media.get("season"),
                    "season_year": media.get("seasonYear"),
                    "episodes": media.get("episodes"),
                    "media_type": media.get("type") or "ANIME",
                    "source_key": identity_key,
                    "source_title": title,
                    "normalized_title": self._normalize_anilist_title(title),
                    "confidence": score / 100,
                    "resolved_at": datetime.datetime.utcnow().isoformat() + "Z",
                    "identity_version": ANILIST_IDENTITY_VERSION,
                    "state": "SYNCABLE",
                    "validated": True,
                }
                with self._anilist_identity_lock:
                    self.anilist_identity_cache[identity_key] = identity.copy()
                    self.save_metadata_cache()
                self.anilist_log(
                    f"[AniList] Identity validated: ID {identity['anilist_id']} "
                    f"({score}% - {reason})"
                )

            if self._anilist_fail_count > 0:
                self._set_health("anilist", "HEALTHY", "AniList request retried successfully")
            self._anilist_fail_count = 0
            self._anilist_backoff_until = 0.0

            if launch_generation is not None and self.media_generation != launch_generation:
                self.log(
                    f"[ANILIST] Discarded stale identity: generation {launch_generation} "
                    f"!= current generation {self.media_generation} (title='{title}')"
                )
            elif (self.current_anilist_identity or {}).get("source_key") == identity_key:
                self._apply_anilist_identity(identity, launch_generation)
        except Exception as exc:
            self._anilist_fail_count += 1
            backoff = min(30 * (2 ** self._anilist_fail_count), 3600)
            self._anilist_backoff_until = time.time() + backoff
            self._set_health("anilist", "DEGRADED", f"AniList identity API error: {exc}")
            if (
                (launch_generation is None or self.media_generation == launch_generation)
                and (self.current_anilist_identity or {}).get("source_key") == identity_key
            ):
                identity = {
                    "source_key": identity_key,
                    "source_title": title,
                    "normalized_title": self._normalize_anilist_title(title),
                    "state": "API_ERROR",
                    "validated": False,
                    "confidence": 0.0,
                    "identity_version": ANILIST_IDENTITY_VERSION,
                }
                self._apply_anilist_identity(identity, launch_generation)
            self.anilist_log(f"[AniList] Identity API error: {exc}")
        finally:
            with self._anilist_identity_lock:
                self._anilist_identity_resolving.discard(identity_key)


    def ensure_anilist_identity(self, title, episode_str, is_music=False):
        """Start identity resolution only for a new anime series/season context."""
        if is_music or not title or not re.search(r"Episode\s*\d+", episode_str or "", re.IGNORECASE):
            return
        identity_key, _, _ = self._anilist_identity_key(title, episode_str)
        current = self.current_anilist_identity or {}
        if current.get("source_key") == identity_key:
            return

        with self._anilist_identity_lock:
            cached = self.anilist_identity_cache.get(identity_key)
            if (
                isinstance(cached, dict)
                and cached.get("identity_version") == ANILIST_IDENTITY_VERSION
                and cached.get("validated")
                and cached.get("confidence", 0) >= ANILIST_IDENTITY_CONFIDENCE / 100
                and cached.get("anilist_id")
            ):
                identity = cached.copy()
                identity["state"] = "SYNCABLE"
                self._apply_anilist_identity(identity)
                self.anilist_log(f"[AniList] Using cached AniList ID {identity['anilist_id']}.")
                return
            legacy_identity = self._legacy_metadata_identity(identity_key, title)
            if legacy_identity:
                self._apply_anilist_identity(legacy_identity)
                return
            if identity_key in self._anilist_identity_resolving:
                return
            self._anilist_identity_resolving.add(identity_key)

        self._apply_anilist_identity({
            "source_key": identity_key,
            "source_title": title,
            "normalized_title": self._normalize_anilist_title(title),
            "state": "RESOLVING",
            "validated": False,
            "confidence": 0.0,
            "identity_version": ANILIST_IDENTITY_VERSION,
        })
        # Capture generation at spawn time so the resolver can discard stale results
        _resolve_gen = self.media_generation
        threading.Thread(
            target=self._resolve_anilist_identity,
            args=(identity_key, title, episode_str, _resolve_gen),
            daemon=True,
        ).start()


    def sync_anilist(self, title, episode_num):
        """Sync only a verified current AniList identity; never title-search here."""
        token = self.config.get("anilist_token", "").strip()
        identity = self.current_anilist_identity or {}
        expected_key, _, _ = self._anilist_identity_key(
            title, self.state_data.get("episode_str", "")
        )
        if time.time() < self._anilist_backoff_until:
            self.anilist_log("[AniList] Circuit open — backing off.")
            return False, "CURRENT"
        if (
            identity.get("source_key") != expected_key
            or identity.get("state") != "SYNCABLE"
            or not identity.get("validated")
            or not identity.get("anilist_id")
        ):
            self.anilist_log("[AniList] Identity is not verified; sync skipped.")
            return False, "CURRENT"
        if not token:
            self.anilist_log("[Error] No AniList token - connect via Integrations tab.")
            return False, "CURRENT"

        total_episodes = identity.get("episodes") or 0
        if episode_num <= 0 or (total_episodes and episode_num > total_episodes):
            self.anilist_log("[AniList] Episode failed identity validation; sync skipped.")
            return False, "CURRENT"

        status = "COMPLETED" if total_episodes and episode_num >= total_episodes else "CURRENT"
        variables = {
            "mediaId": identity["anilist_id"],
            "progress": episode_num,
            "status": status,
        }

        watch_mode = self.state_data.get("watch_mode", "NORMAL")
        if watch_mode == "REWATCH":
            status = "COMPLETED" if total_episodes and episode_num >= total_episodes else "REPEATING"
            variables["status"] = status
            variables["repeat"] = self.state_data.get("rewatch_number", 1)
            mutation = """
            mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus, $repeat: Int) {
              SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: $status, repeat: $repeat) {
                id progress status repeat
              }
            }
            """
        else:
            # Do not send a null repeat argument for normal watching. AniList
            # remains authoritative for an existing completed repeat count.
            mutation = """
            mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus) {
              SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: $status) {
                id progress status repeat
              }
            }
            """
        try:
            response = requests.post(
                "https://graphql.anilist.co",
                json={"query": mutation, "variables": variables},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=10,
            )
            if response.status_code == 401:
                self.config["anilist_token"] = ""
                save_config(self.config)
                self.anilist_log("[Error] Token expired/invalid. Cleared - reconnect via Integrations.")
                return False, "CURRENT"
            payload = response.json()
            entry = ((payload.get("data") or {}).get("SaveMediaListEntry") or {})
            if not entry.get("id"):
                errors = payload.get("errors") or []
                reason = errors[0].get("message", "AniList mutation failed") if errors else "AniList mutation failed"
                self.anilist_log(f"[Error] Mutation failed: {reason}")
                return False, status
            identity["last_synced_episode"] = entry.get("progress")
            identity["last_synced_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            media_list = identity.get("media_list") or {"media": {"id": identity["anilist_id"]}}
            media_list.update({
                "status": entry.get("status", status),
                "progress": entry.get("progress", episode_num),
                "repeat": entry.get("repeat") if entry.get("repeat") is not None else media_list.get("repeat", 0),
            })
            self._apply_anilist_media_list(identity["anilist_id"], media_list, self.media_generation)
            if self._anilist_fail_count > 0:
                self._set_health("anilist", "HEALTHY", "AniList request retried successfully")
            self._anilist_fail_count = 0
            self._anilist_backoff_until = 0.0
            self.anilist_identity_cache[identity["source_key"]] = identity.copy()
            self.save_metadata_cache()
            self.anilist_log(
                f"[OK] Synced AniList ID {identity['anilist_id']}: "
                f"E{entry['progress']} -> {entry['status']}"
            )
            threading.Thread(target=self.force_sync_widget, daemon=True).start()
            threading.Thread(target=self.force_sync_widget_v2, daemon=True).start()
            return True, entry.get("status", status)
        except Exception as exc:
            self._anilist_fail_count += 1
            backoff = min(30 * (2 ** self._anilist_fail_count), 3600)
            self._anilist_backoff_until = time.time() + backoff
            self._set_health("anilist", "DEGRADED", f"AniList sync failed: {exc}")
            return False, status


    def force_sync_widget(self):


        token = self.config.get("anilist_token")


        client_id = self.config.get("discord_app_id")


        access_token = self.config.get("discord_access_token")


        if not token or not client_id or not access_token:


            self.send_webhook_log("âŒ **Discord Widget Skipped:** Missing token, app ID, or access token in settings.")


            return


        try:


            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'Accept': 'application/json'}


            query = '{ Viewer { statistics { anime { episodesWatched minutesWatched meanScore statuses { status count } } } } }'


            r = requests.post('https://graphql.anilist.co', json={'query': query}, headers=headers, timeout=10)


            


            if r.status_code != 200:


                self.send_webhook_log(f"âŒ **Discord Widget Failed:** AniList stats fetch returned HTTP {r.status_code}")


                return


            


            body = r.json()


            data = body.get('data') or {}


            viewer = data.get('Viewer') or {}


            statistics = viewer.get('statistics') or {}


            stats = statistics.get('anime') or {}


            


            if not stats:


                self.send_webhook_log(f"âŒ **Discord Widget Failed:** AniList returned empty stats. Raw response: `{r.text[:150]}`")


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


                self.send_webhook_log(f"âŒ **Discord Widget Failed:** HTTP {r2.status_code} — `{r2.text[:150]}`")


        except Exception as e:


            pass


            self.send_webhook_log(f"âŒ **Discord Widget Crashed:** `{e}`")





    def force_sync_widget_v2(self):


        token = self.config.get("anilist_token")


        bot_token = self.config.get("discord_widget_bot_token")


        app_id = self.config.get("discord_widget_app_id")


        user_id = self.config.get("discord_widget_user_id")





        if not token or not bot_token or not app_id or not user_id:


            return





        try:


            self.log("Syncing Profile Widget v2 stats...")


            # 1. Fetch AniList Stats


            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'Accept': 'application/json'}


            query = '{ Viewer { name statistics { anime { episodesWatched minutesWatched meanScore statuses { status count } } } } }'


            r = requests.post('https://graphql.anilist.co', json={'query': query}, headers=headers, timeout=10)


            if r.status_code != 200:


                self.log(f"Widget v2 Failed: AniList HTTP {r.status_code}")


                self.send_webhook_log(f"âŒ **Widget v2 Failed:** AniList HTTP {r.status_code}")


                return


            


            body = r.json()


            viewer = body.get('data', {}).get('Viewer', {})


            anilist_name = viewer.get('name', 'User')


            stats = viewer.get('statistics', {}).get('anime', {})


            


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





            # 2. Push to Discord Profile Widget


            payload = {


                "username": anilist_name,


                "data": {


                    "dynamic": [


                        {"type": 1, "name": "completed", "value": str(completed)},


                        {"type": 1, "name": "watching", "value": str(watching)},


                        {"type": 1, "name": "planned", "value": str(planned)},


                        {"type": 1, "name": "episodes", "value": str(episodes)},


                        {"type": 1, "name": "hours", "value": str(minutes // 60)},


                        {"type": 1, "name": "mean_score", "value": str(mean)}


                    ]


                }


            }





            discord_headers = {


                'Authorization': f'Bot {bot_token}',


                'Content-Type': 'application/json',


                'User-Agent': 'DiscordBot (https://github.com/discord/discord-api-docs, 1.0.0)'


            }


            url = f"https://discord.com/api/v9/applications/{app_id}/users/{user_id}/identities/0/profile"


            


            r2 = requests.patch(url, json=payload, headers=discord_headers, timeout=5)


            if r2.status_code in (200, 204):


                self.log(f"Successfully updated Profile Widget v2 (Episodes: {episodes})")


                self.send_webhook_log(f"✅ **Widget v2 Updated!** (Episodes: {episodes})")


            else:


                self.log(f"Widget v2 Failed: HTTP {r2.status_code} — {r2.text[:150]}")


                self.send_webhook_log(f"âŒ **Widget v2 Failed:** HTTP {r2.status_code} — `{r2.text[:150]}`")


        except Exception as e:


            self.log(f"Widget v2 Crashed: {e}")


            self.send_webhook_log(f"âŒ **Widget v2 Crashed:** `{e}`")





    def fetch_anilist_score_format(self):


        """Fetch the user's scoring system from AniList and cache it in state_data."""


        token = self.config.get("anilist_token", "").strip()


        if not token:


            return


        try:


            r = requests.post(


                "https://graphql.anilist.co",


                json={"query": "query { Viewer { mediaListOptions { scoreFormat } } }"},


                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},


                timeout=8


            )


            if r.status_code == 200:


                fmt = (r.json().get("data") or {}).get("Viewer", {}).get("mediaListOptions", {}).get("scoreFormat", "POINT_100")


                if fmt:


                    self.state_data["anilist_score_format"] = fmt


                    self.log(f"[AniList] Score format: {fmt}")


        except Exception:


            pass





    def fetch_aniskip_timestamps(self, anilist_id, episode_num):


        """Fetch OP/ED timestamps from AniSkip API. Cached by (anilist_id, episode)."""


        cache_key = (anilist_id, episode_num)


        if cache_key in self.aniskip_cache:


            return self.aniskip_cache[cache_key]


        try:


            url = f"https://api.aniskip.com/v1/skip-times/{anilist_id}/{episode_num}?types=op&types=ed"


            r = requests.get(url, timeout=6)


            if r.status_code == 200:


                data = r.json()


                result = {"op": None, "ed": None}


                for item in data.get("results", []):


                    skip_type = item.get("skip_type")


                    interval = item.get("interval", {})


                    start = interval.get("start_time")


                    end = interval.get("end_time")


                    if start is not None and end is not None:


                        result[skip_type] = {"start": start, "end": end}


                self.aniskip_cache[cache_key] = result


                return result


            else:


                self.aniskip_cache[cache_key] = {"op": None, "ed": None}


        except Exception:


            self.aniskip_cache[cache_key] = {"op": None, "ed": None}


        return self.aniskip_cache.get(cache_key, {"op": None, "ed": None})





    def check_aniskip(self):


        """Check current playback position against AniSkip timestamps. Notify or auto-skip."""


        if not self.config.get("anilist_token"):


            return


        if self.state_data.get("playback_state") != "playing":


            return


        if self.state_data.get("is_music"):


            return





        metadata = self.state_data.get("metadata") or {}


        identity = self.current_anilist_identity or {}


        anilist_id = (
            identity.get("anilist_id")
            if identity.get("state") == "SYNCABLE" and identity.get("validated")
            else metadata.get("anilistId")
        )


        if not anilist_id:


            return





        ep_str = self.state_data.get("episode_str", "")


        ep_match = re.search(r'Episode\s*(\d+)', ep_str, re.IGNORECASE)


        if not ep_match:


            return


        episode_num = int(ep_match.group(1))


        title = self.state_data.get("cleaned_title", "")


        current_time = self.state_data.get("time", 0)





        timestamps = self.fetch_aniskip_timestamps(anilist_id, episode_num)





        def _in_range(section):


            seg = timestamps.get(section)


            if not seg:


                return False


            return seg["start"] <= current_time <= seg["end"]





        for section, label in [("op", "Opening"), ("ed", "Ending")]:


            seg = timestamps.get(section)


            if not seg:


                continue


            notify_key = (title, episode_num, section)


            if _in_range(section):


                if notify_key not in self.aniskip_notified:


                    self.aniskip_notified.add(notify_key)


                    end_fmt = time.strftime("%M:%S", time.gmtime(seg["end"]))


                    if self.config.get("aniskip_auto_skip"):


                        # Auto-skip: seek to end of section via VLC HTTP API


                        try:


                            host = self.config.get("vlc_host", "localhost")


                            port = self.config.get("vlc_port", 8080)


                            password = self.config.get("vlc_password", "")


                            seek_url = f"http://{host}:{port}/requests/status.xml?command=seek&val={int(seg['end'])}s"


                            requests.get(seek_url, auth=HTTPBasicAuth("", password), timeout=3)


                            show_toast("AniSkip", f"Auto-skipped {label}! Jumped to {end_fmt}", icon="skip")


                            self.log(f"[AniSkip] Auto-skipped {label} at {current_time:.0f}s → {seg['end']:.0f}s")


                        except Exception as e:


                            self.log(f"[AniSkip] Auto-skip failed: {e}")


                    else:


                        show_toast(f"AniSkip — {label} Detected", f"Ends at {end_fmt}", icon="skip")


                        self.log(f"[AniSkip] {label} detected in '{title}' E{episode_num}")





    def show_score_popup(self, title, episode_num, media_id):


        """Show a scoring popup when user finishes an anime by routing it to the safe UI worker."""


        score_key = (title, episode_num)


        if score_key in self.scored_episodes:


            return


        if not self.config.get("auto_score_popup", True):


            return





        self.scored_episodes.add(score_key)


        fmt = self.state_data.get("anilist_score_format", "POINT_100")





        token = self.config.get("anilist_token", "")





        if _notifier_client.proc:


            try:


                import json


                data = json.dumps({


                    "type": "score_popup",


                    "title": title,


                    "media_id": media_id,


                    "format": fmt,


                    "token": token


                })


                _notifier_client.proc.stdin.write(data + "\n")


                _notifier_client.proc.stdin.flush()


            except Exception as e:


                self.log(f"Failed to trigger score popup: {e}")


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





        identity = self.current_anilist_identity or {}
        expected_key, _, _ = self._anilist_identity_key(title, ep_str)
        if time.time() < self._anilist_backoff_until:
            self.anilist_log("[AniList] Circuit open — backing off.")
            return False, "CURRENT"
        if (
            identity.get("source_key") != expected_key
            or identity.get("state") != "SYNCABLE"
            or not identity.get("validated")
            or not identity.get("anilist_id")
        ):
            # Resolution runs independently; do not turn every VLC poll into a
            # failed threshold event while it is still pending or rejected.
            return


        # Deduplicate by AniList media ID and rewatch cycle. This keeps seasons
        # isolated and allows episode one to sync in a later, explicit rewatch.


        cache_key = f"{identity['anilist_id']}:E{episode_num}:R{self.state_data.get('rewatch_number', 0)}"


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
            success, new_status = self.sync_anilist(title, episode_num)


            if success:


                show_toast("AniList Synced!", f"{title} • Episode {episode_num}", icon="sync")


                # Check if this was the final episode or marked COMPLETED → show score popup


                identity = self.current_anilist_identity or {}


                total_eps = identity.get("episodes") or 0


                media_id = identity.get("anilist_id")


                if (new_status == "COMPLETED" or (total_eps and episode_num >= total_eps)) and media_id:


                    threading.Thread(target=self.show_score_popup, args=(title, episode_num, media_id), daemon=True).start()


            else:


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


                                backend_ref.send_webhook_log(f"âŒ **AniList OAuth Failed:** {err_msg}")


                                self._respond(400, f'{{"success": false, "error": "{err_msg}"}}'.encode(), "application/json")


                        except Exception as e:


                            pass


                            backend_ref.send_webhook_log(f"âŒ **AniList OAuth Error:** {str(e)}")


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


            self.log(f"OAuth Server Error: {e}")








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





    def normalize_cover_url(self, url):


        """Return a Discord/UI-safe image URL, or None if it is not usable."""


        if not url or not isinstance(url, str):


            return None





        url = url.strip()


        if url.startswith("data:image/"):


            return url





        url = ensure_https(url)


        parsed = urllib.parse.urlparse(url)


        if parsed.scheme not in ("http", "https") or not parsed.netloc:


            return None





        headers = {


            "User-Agent": f"VLC-RPC/{CURRENT_VERSION}",


            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",


        }


        try:


            r = requests.get(url, headers=headers, stream=True, timeout=5, allow_redirects=True)


            content_type = (r.headers.get("Content-Type") or "").split(";")[0].lower()


            final_url = ensure_https(r.url)


            status_ok = 200 <= r.status_code < 300


            r.close()


            if status_ok and content_type.startswith("image/"):


                return final_url


            if status_ok and re.search(r'\.(jpg|jpeg|png|webp|gif)(?:$|\?)', urllib.parse.urlparse(final_url).path, re.I):


                return final_url


            self.log(f"[Metadata] Rejected non-image cover URL: {url}")


            return None


        except Exception:


            # Some CDNs block validation requests but still render fine in Discord/WebView.


            # Keep plausible direct image URLs instead of deleting otherwise good covers.


            if parsed.scheme == "https" and re.search(r'\.(jpg|jpeg|png|webp|gif)(?:$|\?)', parsed.path, re.I):


                return url


            return None





    def prepare_metadata_cover(self, metadata):


        if not metadata:


            return None


        if not isinstance(metadata, dict):


            return None


        metadata = dict(metadata)


        image_url = self.normalize_cover_url(metadata.get("image_url"))


        metadata["image_url"] = image_url  # kept as raw HTTPS URL for Discord RPC





        # Also produce a base64 data URI so the pywebview frontend can display


        # the image without being blocked by the file:// → https:// CORS restriction.


        if image_url and not image_url.startswith("data:image/"):


            try:


                import base64


                headers = {


                    "User-Agent": f"VLC-RPC/{CURRENT_VERSION}",


                    "Accept": "image/*,*/*;q=0.8",


                }


                r = requests.get(image_url, headers=headers, timeout=6, allow_redirects=True)


                if 200 <= r.status_code < 300:


                    mime = (r.headers.get("Content-Type") or "image/jpeg").split(";")[0].lower()


                    if not mime.startswith("image/"):


                        mime = "image/jpeg"


                    metadata["image_data_uri"] = f"data:{mime};base64," + base64.b64encode(r.content).decode()


            except Exception:


                pass  # Frontend will fall back to the raw URL or local VLC art


        elif image_url and image_url.startswith("data:image/"):


            metadata["image_data_uri"] = image_url  # already a data URI





        return metadata








    def fetch_anilist_username(self):


        """Fetch the AniList username for the connected account. Cached after first success.


        Returns the username string, or None if not connected / fetch fails."""


        if self.anilist_username_cache is not None:


            # False means we already tried and failed — don't retry every poll


            return self.anilist_username_cache if self.anilist_username_cache else None


        token = self.config.get("anilist_token", "").strip()


        if not token:


            self.anilist_username_cache = False


            return None


        try:


            r = requests.post(


                "https://graphql.anilist.co",


                json={"query": "query { Viewer { name } }"},


                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},


                timeout=8


            )


            if r.status_code == 200:


                name = (r.json().get("data") or {}).get("Viewer", {}).get("name", "")


                if name:


                    self.anilist_username_cache = name


                    self.log(f"[AniList] Cached username: {name}")


                    return name


        except Exception:


            pass


        self.anilist_username_cache = False


        return None





    def _capture_scene_snapshot(self, file_path, time_secs):


        """Use ffmpeg to grab the current video frame and upload it to Imgur.


        Updates state_data['scene_snapshot_url'] on success. Logs errors to Live Logs."""


        import subprocess


        try:


            # On Windows, CREATE_NO_WINDOW ensures ffmpeg doesn't flash a console


            # window and also works correctly in --noconsole PyInstaller builds.


            creationflags = 0


            if hasattr(subprocess, 'CREATE_NO_WINDOW'):


                creationflags = subprocess.CREATE_NO_WINDOW





            # Build the ffmpeg command: seek to time_secs, output 1 JPEG frame to stdout


            cmd = [


                "ffmpeg", "-y",


                "-ss", str(int(time_secs)),


                "-i", file_path,


                "-vframes", "1",


                "-vf", "scale=1280:-1",


                "-f", "image2pipe",


                "-vcodec", "mjpeg",


                "pipe:1"


            ]


            result = subprocess.run(


                cmd, capture_output=True, timeout=15,


                creationflags=creationflags


            )


            if result.returncode != 0 or not result.stdout:


                stderr_msg = result.stderr.decode('utf-8', errors='replace')[-300:] if result.stderr else 'no output'


                self.log(f"[Snapshot] ffmpeg failed (code {result.returncode}): {stderr_msg}")


                return





            # Store the raw image as base64 for the webview frontend to avoid CORS issues


            import base64


            snapshot_b64 = "data:image/jpeg;base64," + base64.b64encode(result.stdout).decode('utf-8')


            self.state_data['scene_snapshot_data_uri'] = snapshot_b64





            # Upload to Imgur (free, direct hotlinking) for Discord RPC


            upload = requests.post(


                "https://api.imgur.com/3/image",


                headers={"Authorization": "Client-ID 546c25a59c58ad7"},


                files={"image": ("snapshot.jpg", result.stdout, "image/jpeg")},


                timeout=15


            )


            if upload.status_code == 200:


                json_resp = upload.json()


                url = json_resp.get("data", {}).get("link", "")


                if url:


                    self.state_data["scene_snapshot_url"] = ensure_https(url)


                    self.log(f"[Snapshot] Uploaded scene snapshot: {url}")
                    if self.state_data.get("health", {}).get("ffmpeg") != "HEALTHY":
                        self._set_health("ffmpeg", "HEALTHY")


                else:


                    self.log(f"[Snapshot] Upload failed: Invalid response format")


            else:


                self.log(f"[Snapshot] Upload failed: {upload.status_code} - {upload.text}")


        except FileNotFoundError:


            # ffmpeg not on PATH — disable silently so we don't spam the log


            self._set_health("ffmpeg", "UNAVAILABLE", "FFmpeg not found — scene snapshots disabled.")


            # Turn off the feature so we don't keep trying


            self.config["scene_snapshots"] = False


        except Exception as e:


            self.log(f"[Snapshot] Capture failed (non-fatal): {e}")





    def set_window(self, window):


        self.window = window





    # ─────────────────────────────────────────────────────────────────────────
    # Metadata Cache Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize_cache_key(self, s):
        """Lowercase, strip punctuation, collapse whitespace for collision-resistant cache keys."""
        import unicodedata
        s = s.lower().strip()
        # Remove common articles that differ between file names and API titles
        s = re.sub(r'\b(the|a|an)\b', '', s)
        # Keep alphanumeric and spaces only
        s = re.sub(r'[^\w\s]', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def _build_cache_key(self, media_type, cleaned_title, episode_str, artist=""):
        """Build a normalized, collision-resistant cache key."""
        norm = self._normalize_cache_key(cleaned_title)
        if media_type == "music":
            norm_artist = self._normalize_cache_key(artist) if artist else ""
            return f"music:{norm}:{norm_artist}"
        # Parse season/episode from episode_str for structured keys
        se = re.search(r'Season\s*(\d+)\s*Episode\s*(\d+)', episode_str or "", re.IGNORECASE)
        ep = re.search(r'Episode\s*(\d+)', episode_str or "", re.IGNORECASE)
        if se:
            s_num, e_num = se.group(1), se.group(2)
        elif ep:
            s_num, e_num = "1", ep.group(1)
        else:
            s_num, e_num = None, None
        if media_type == "anime":
            if s_num and int(s_num) > 1:
                return f"anime:{norm}:S{s_num}"
            return f"anime:{norm}"
        if media_type == "movie":
            year_m = re.search(r'\((\d{4})\)', episode_str or "")
            year = year_m.group(1) if year_m else ""
            return f"movie:{norm}:{year}"
        if media_type == "tv_show":
            if s_num and e_num:
                return f"tvshow:{norm}:S{s_num}E{e_num}"
            return f"tvshow:{norm}"
        # Fallback
        return f"{media_type}:{norm}"

    def _is_valid_cache_entry(self, entry):
        """
        Return True only if this cache entry is usable.
        Negative markers are valid (caller decides how to handle them).
        """
        if not isinstance(entry, dict):
            return False
        # Version check — reject old schema entries
        ver = entry.get("_cache_version")
        if ver is not None and ver != METADATA_CACHE_VERSION:
            return False
        # Negative marker: valid but signals failure
        if entry.get("_negative"):
            return True
        # Real metadata: must have at least a title
        if not (entry.get("title") or entry.get("official_title")):
            return False
        return True

    def _is_negative_expired(self, entry):
        """Return True if a negative cache marker is old enough to retry (1 hour)."""
        ts = entry.get("_negative_ts", 0)
        return (time.time() - ts) > 3600

    def _merge_metadata(self, base, update):
        """
        Merge update dict into base dict. Only overwrite a field if:
          - the new value is not None
          - the new value is not an empty string / empty list
        This prevents a provider returning None from erasing a valid cover/rating.
        """
        if not base:
            return dict(update) if update else {}
        if not update:
            return dict(base)
        merged = dict(base)
        for k, v in update.items():
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            if isinstance(v, list) and not v:
                continue
            merged[k] = v
        return merged

    def _get_cache_path(self):
        """Return the resolved metadata cache file path."""
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(application_path, CACHE_FILE)

    def load_metadata_cache(self):
        if hasattr(self, "state_data") and "health" in self.state_data:
            self.state_data["health"]["cache"] = "HEALTHY"
        cache_path = self._get_cache_path()
        if not os.path.exists(cache_path):
            return {}

        # Read raw bytes first — if file is empty or truncated, handle gracefully
        try:
            raw = open(cache_path, "r", encoding="utf-8").read().strip()
        except Exception as e:
            self.log(f"[RECOVERY] Metadata cache repaired — could not read file: {e}")
            if hasattr(self, "state_data") and "health" in self.state_data: self.state_data["health"]["cache"] = "REPAIRED"
            return {}

        if not raw:
            self.log("[RECOVERY] Metadata cache repaired — file was empty")
            if hasattr(self, "state_data") and "health" in self.state_data: self.state_data["health"]["cache"] = "REPAIRED"
            return {}

        # Parse JSON
        try:
            data = json.loads(raw)
        except Exception as e:
            self.log(f"[RECOVERY] Metadata cache repaired — JSON parse failed ({e}); backing up bad file")
            if hasattr(self, "state_data") and "health" in self.state_data: self.state_data["health"]["cache"] = "REPAIRED"
            try:
                bak = cache_path + ".bak"
                import shutil
                shutil.copy2(cache_path, bak)
            except Exception:
                pass
            return {}

        if not isinstance(data, dict):
            self.log("[RECOVERY] Metadata cache repaired — root was not a dict")
            if hasattr(self, "state_data") and "health" in self.state_data: self.state_data["health"]["cache"] = "REPAIRED"
            return {}

        # Migrate: strip entries with incompatible schema versions
        cleaned = {}
        migrated_count = 0
        for k, v in data.items():
            # Always keep the AniList identity block — it has its own versioning
            if k == ANILIST_IDENTITY_CACHE_KEY:
                cleaned[k] = v
                continue
            if not isinstance(v, dict):
                migrated_count += 1
                continue
            entry_ver = v.get("_cache_version")
            if entry_ver is not None and entry_ver != METADATA_CACHE_VERSION:
                migrated_count += 1
                continue
            cleaned[k] = v

        if migrated_count:
            self.log(f"[METADATA] Cache migrated — discarded {migrated_count} old-schema entries")

        return cleaned





    def save_metadata_cache(self):
        """Write metadata cache atomically using a temp file + os.replace."""
        cache_path = self._get_cache_path()
        tmp_path = cache_path + ".tmp"

        with self._metadata_cache_lock:
            # Snapshot dict to avoid mutation-during-serialization
            snap = dict(self.metadata_cache)

        # Stamp each real entry with the current cache version
        for k, v in snap.items():
            if isinstance(v, dict) and k != ANILIST_IDENTITY_CACHE_KEY:
                v["_cache_version"] = METADATA_CACHE_VERSION

        # Keep AniList identity records alongside metadata
        snap[ANILIST_IDENTITY_CACHE_KEY] = dict(self.anilist_identity_cache)

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(snap, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, cache_path)
        except Exception as e:
            self.log(f"[METADATA] Cache save failed: {e}")
            try:
                os.remove(tmp_path)
            except Exception:
                pass








    def _fetch_metadata_bg(self, cache_key, cleaned_title, episode_str, is_music, artist, input_uri="", media_type_hint=""):

        """Fetch metadata in a background thread so the main loop stays fast."""

        # Capture the generation at launch time. If the user changes tracks
        # before providers finish, we discard the result instead of caching
        # wrong metadata under this key.
        entry_generation = getattr(self, 'media_generation', 0)

        try:


            season_num = None


            episode_num = None


            # Use passed media_type to avoid race with state_data being updated for a new file


            media_type = media_type_hint or self.state_data.get("media_type", "movie")





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





            search_title = cleaned_title





            self.log(f"[Metadata] Fetching '{search_title}' type={media_type} S{season_num}E{episode_num}")





            def prepared(candidate):


                return self.prepare_metadata_cover(candidate)





            metadata = None


            # Try ALL sources in priority order. AniList is now universal fallback


            # because many anime are misclassified as tv_show/movie.


            if media_type == "music":


                metadata = prepared(self.fetch_itunes_metadata(search_title, artist))





            elif media_type == "movie":


                metadata = prepared(self.fetch_omdb_metadata(search_title, year))


                if not metadata or not metadata.get("image_url"):


                    metadata = prepared(self.fetch_anilist_metadata(search_title))


                if not metadata or not metadata.get("image_url"):


                    metadata = prepared(self.fetch_jikan_metadata(search_title))





            elif media_type == "anime":


                # AniList: best English title matching + season-aware


                if season_num and season_num > 1:


                    ordinals = {2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}


                    suffix = ordinals.get(season_num, f"{season_num}th")


                    metadata = prepared(self.fetch_anilist_metadata(f"{search_title} {suffix} Season"))


                if not metadata or not metadata.get("image_url"):


                    metadata = prepared(self.fetch_anilist_metadata(search_title))


                # Jikan fallback


                if not metadata or not metadata.get("image_url"):


                    if season_num and season_num > 1:


                        ordinals = {2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}


                        suffix = ordinals.get(season_num, f"{season_num}th")


                        metadata = prepared(self.fetch_jikan_metadata(f"{search_title} {suffix} Season"))


                if not metadata or not metadata.get("image_url"):


                    metadata = prepared(self.fetch_jikan_metadata(search_title))


                # Supplement rating from OMDb if missing


                if metadata and not metadata.get("rating"):


                    omdb = self.fetch_omdb_metadata(search_title, year)


                    if omdb and omdb.get("rating"):


                        metadata["rating"] = omdb["rating"]





            elif media_type == "tv_show":


                metadata = prepared(self.fetch_tvmaze_metadata(search_title, season_num=season_num, episode_num=episode_num))


                


                # If TVMaze found it but it's classified as Anime/Animation, 


                # AniList usually has vastly superior covers, genres, and ratings.


                if metadata and any(g.lower() in ("anime", "animation") for g in metadata.get("genres", [])):


                    anilist_meta = prepared(self.fetch_anilist_metadata(search_title))


                    if anilist_meta and anilist_meta.get("image_url"):


                        metadata = anilist_meta





                if not metadata or not metadata.get("image_url"):


                    metadata = prepared(self.fetch_omdb_metadata(search_title, year))


                if not metadata or not metadata.get("image_url"):


                    metadata = prepared(self.fetch_anilist_metadata(search_title))


                if not metadata or not metadata.get("image_url"):


                    metadata = prepared(self.fetch_jikan_metadata(search_title))





            if not metadata or not metadata.get("image_url"):


                metadata = prepared(self.fetch_wikipedia_metadata(search_title))





            if metadata and metadata.get("image_url"):


                self.log(f"[Metadata] OK Cover found for '{search_title}'")


            else:


                self.log(f"[Metadata] NO Cover found for '{search_title}'")





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





            # ── Generation guard (primary) ─────────────────────────────────────
            # Covers the same-file/different-session race:
            # Generation N:  file A starts → metadata worker launched.
            # Generation N+1: same file A stopped and restarted.
            # Without this guard, still_same_file would pass (input_uri is
            # identical) and the stale Gen-N result would overwrite Gen-N+1 state.
            if self.media_generation != entry_generation:
                self.log(
                    f"[METADATA] Discarded stale result: generation {entry_generation} "
                    f"!= current generation {self.media_generation} "
                    f"(title='{cleaned_title}')"
                )
                return

            # ── File-URI guard (secondary) ────────────────────────────────────────
            # Only apply metadata if the user is still on the same file.
            # Use input_uri (the file path) rather than rebuilding current_key from
            # volatile state — this prevents the race where track_key has moved on
            # but input_uri hasn't changed (same file, title just got resolved by Gemini).
            still_same_file = (
                not input_uri  # backwards compat: old calls without input_uri always apply
                or self.state_data.get("_last_art_key", "") == input_uri
                or self.state_data.get("_last_art_uri", "") == input_uri
            )

            if still_same_file:


                self.state_data["metadata"] = metadata


                self.state_data["local_image_path"] = metadata.get("image_url") if metadata else None


                self.state_data["status_message"] = "Metadata loaded successfully."


                # â”€â”€ Official title override â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


                # Every metadata source (AniList, OMDb, TVMaze, Jikan) now returns


                # an "official_title" field with the authoritative database name.


                # We override the display title with it so regardless of how the


                # user named their file, the UI always shows the correct title.


                if metadata:
                    official = metadata.get("official_title")
                    if official and isinstance(official, str) and official.strip():
                        self.log(f"[Metadata] Title resolved: '{cleaned_title}' → '{official.strip()}'")

                self.log(f"[Metadata] Applied metadata for '{cleaned_title}'")
                if cache_key in self._metadata_neg_cache:
                    del self._metadata_neg_cache[cache_key]
                    self._set_health("metadata", "HEALTHY", "Metadata fetching restored")





            else:


                self.log(f"[STATE] Discarded stale metadata fetch for '{search_title}' (generation changed)")


        except Exception as e:


            fail_count = self._metadata_neg_cache.get(cache_key, (0, 0))[1] + 1
            self._metadata_neg_cache[cache_key] = (time.time(), fail_count)
            self._set_health("metadata", "DEGRADED", f"Metadata fetch cascade failed ({e}) — negative cache active")
            self.state_data["status_message"] = f"Metadata fetch failed: {e}"








    def _set_health(self, subsystem, status, message=None):
        self.state_data.setdefault("health", {})[subsystem] = status
        if message:
            self.log(f"[RECOVERY] {message}")

    def rpc_worker(self):


        asyncio.set_event_loop(asyncio.new_event_loop())


        last_track_key = None


        


        # Fetch the user's AniList score format once at startup


        threading.Thread(target=self.fetch_anilist_score_format, daemon=True).start()





        while not self.state_data["exit_flag"]:


            try:


                auth = HTTPBasicAuth('', self.config.get("vlc_password", ""))


                url = f"http://{self.config.get('vlc_host', 'localhost')}:{self.config.get('vlc_port', 8080)}/requests/status.json"


                r = requests.get(url, auth=auth, timeout=2)


                r.encoding = 'utf-8'


                


                if r.status_code == 200:


                    vlc_data = r.json()


                    if not self.state_data.get("vlc_connected"):
                        self._set_health("vlc", "HEALTHY", "VLC connection restored")
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
                    now_playing = meta.get("now_playing", "")


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





                    # --- Offline cover: read VLC's embedded artwork as base64 ---


                    # Track artwork by the strongest available media identity. VLC can


                    # leave meta.url empty/stale, so filename and playlist id are used


                    # as fallbacks to prevent previous-episode cover bleed.


                    art_identity = input_uri or file_name or current_plid


                    _last_art_key = self.state_data.get("_last_art_key", "")


                    if art_identity != _last_art_key:


                        # New file - clear old online/offline art immediately while new


                        # metadata is resolving, so the UI never shows the previous item.


                        self.state_data["_last_art_key"] = art_identity


                        self.state_data["_last_art_uri"] = input_uri


                        self.state_data["metadata"] = None


                        self.state_data["local_image_path"] = None


                        self.state_data["scene_snapshot_url"] = ""  # clear snapshot for new file


                        self.state_data["scene_snapshot_data_uri"] = ""


                        self.state_data["snapshot_id"] = ""


                        art_data_uri = ""


                        vlc_art_url = meta.get("artwork_url", "")


                        try:


                            if vlc_art_url and vlc_art_url.startswith("file:///"):


                                import base64, mimetypes


                                art_path = urllib.parse.unquote(vlc_art_url[8:]).replace("/", os.sep)


                                if os.path.isfile(art_path):


                                    mime = mimetypes.guess_type(art_path)[0] or "image/jpeg"


                                    with open(art_path, "rb") as af:


                                        art_data_uri = f"data:{mime};base64," + base64.b64encode(af.read()).decode()


                            if not art_data_uri:


                                import base64


                                vlc_host = self.config.get("vlc_host", "localhost")


                                vlc_port = self.config.get("vlc_port", 8080)


                                vlc_pw = self.config.get("vlc_password", "")


                                ar = requests.get(


                                    f"http://{vlc_host}:{vlc_port}/art",


                                    auth=HTTPBasicAuth("", vlc_pw), timeout=2


                                )


                                if ar.status_code == 200 and ar.headers.get("Content-Type", "").startswith("image"):


                                    mime = ar.headers["Content-Type"].split(";")[0]


                                    art_data_uri = f"data:{mime};base64," + base64.b64encode(ar.content).decode()


                        except Exception:


                            pass


                        self.state_data["local_arturl"] = art_data_uri


                    # else: same file, keep existing local_arturl (avoids flicker on Gemini title resolve)





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


                        cached = self.gemini_cache.get(raw_name)


                        last_fail = self.gemini_fail_times.get(raw_name, 0)


                        # Spawn a new thread if: never tried, OR last failure was >60s ago


                        should_try = (


                            raw_name not in self.gemini_cache


                            or (cached is None and time.time() - last_fail > 3600)


                        )


                        if should_try:


                            self.gemini_cache[raw_name] = "pending"


                            # Default-arg trick captures launch_generation at definition time
                            # (Python closure semantics) — not at call time.
                            def _run_gemini(name, key, _launch_gen=self.media_generation):


                                t, e, mt = media_identity_to_display(query_gemini_title(name, key))


                                if t:
                                    # Generation guard: discard if media changed while Gemini was resolving
                                    if self.media_generation != _launch_gen:
                                        self.log(
                                            f"[STATE] Discarded stale Gemini result for '{name}' "
                                            f"(gen {_launch_gen} -> {self.media_generation})"
                                        )
                                        return


                                    self.gemini_cache[name] = (t, e, mt or "")


                                    self.anilist_log(f"[Gemini AI] Match: {t} {e}")
                                    if self.state_data.get("health", {}).get("gemini") != "HEALTHY":
                                        self._set_health("gemini", "HEALTHY")


                                    try:
                                        _gc_tmp = self.gemini_cache_file + '.tmp'
                                        with self._gemini_cache_lock:
                                            _gc_snap = {k: list(v) if isinstance(v, tuple) else v
                                                        for k, v in self.gemini_cache.items()
                                                        if v is not None and v != 'pending'}
                                        with open(_gc_tmp, 'w', encoding='utf-8') as gcf:
                                            json.dump(_gc_snap, gcf, ensure_ascii=False)
                                            gcf.flush()
                                            os.fsync(gcf.fileno())
                                        os.replace(_gc_tmp, self.gemini_cache_file)
                                    except Exception:
                                        pass


                                else:


                                    # Don't permanently block - allow retry after 1 hour


                                    self.gemini_cache[name] = None


                                    self.gemini_fail_times[name] = time.time()


                                    self._set_health("gemini", "DEGRADED", "Gemini unavailable; using deterministic parser")


                            threading.Thread(target=_run_gemini, args=(raw_name, gemini_key), daemon=True).start()





                        cached = self.gemini_cache.get(raw_name)


                        if cached and cached != "pending":


                            cleaned_title, episode_str = cached[0], cached[1]


                            ai_media_type = cached[2] if len(cached) > 2 else ""


                            # Map Gemini media_type to our internal types


                            if ai_media_type in ("anime", "ova", "special"):


                                media_type = "anime"


                            elif ai_media_type == "movie":


                                media_type = "movie"


                            elif ai_media_type in ("tv",):


                                media_type = "tv_show"


                            elif ai_media_type in ("song", "music_video"):


                                media_type = "music"





                    if not cleaned_title:


                        cleaned_title, episode_str, _ = media_identity_to_display(clean_title(raw_name))





                    if tag_title and not episode_str:


                        alt_title, alt_episode, _ = media_identity_to_display(clean_title(tag_title))


                        if alt_episode:


                            episode_str = alt_episode


                        if not cleaned_title:


                            cleaned_title = alt_title





                    # Only override media_type if Gemini hasn't already set it


                    if media_type != "music" and media_type != "anime":


                        if "Episode" in episode_str or "Season" in episode_str:


                            media_type = "tv_show"


                    


                    self.state_data["media_type"] = media_type


                    is_music = (media_type == "music")


                    self.state_data["is_music"] = is_music


                    self.state_data["cleaned_title"] = cleaned_title


                    # CRITICAL: update episode_str every poll cycle so check_auto_sync always has it


                    # For music files, guessit may return episode_str="Movie"; clear it so the


                    # frontend shows the artist name instead of a misleading "Movie" subtitle.


                    if is_music and episode_str and "Movie" in episode_str:


                        episode_str = ""


                    self.state_data["episode_str"] = episode_str


                    # track_key only uses STABLE identifiers: playlist ID, file path, filename, and now_playing.
                    # Resolved titles (Gemini) or dynamic episodes are excluded because
                    # they update mid-playback and cause false media boundaries, which
                    # destroys rewatch state and triggers spurious metadata fetches.
                    track_key = f"{current_plid}:{input_uri}:{file_name}:{now_playing}"
                    # Resolve once per normalized series/season identity. The resolver
                    # is asynchronous and auto-sync will wait for SYNCABLE state.
                    self.ensure_anilist_identity(cleaned_title, episode_str, is_music)





                    # Don't trigger metadata fetch if Gemini is still pending —


                    # wait for it to resolve so we get the correct title and type.


                    gemini_pending = (gemini_key and self.gemini_cache.get(raw_name) == "pending")





                    if self.force_update_flag:


                        last_track_key = None


                        self.force_update_flag = False





                    self.check_auto_sync()
                    self._check_rewatch_signals()

                    self.check_aniskip()





                    if track_key != last_track_key and not gemini_pending:


                        if hasattr(self, 'last_watched_title_raw') and self.last_watched_title_raw != self.state_data['title']:


                            self.add_to_history(self.last_watched_title, self.last_watched_ep, self.last_watched_music, self.current_watch_duration)


                            self.current_watch_duration = 0





                        self.last_watched_title_raw = self.state_data['title']


                        self.last_watched_title = cleaned_title


                        self.last_watched_ep = episode_str


                        self.last_watched_music = is_music


                        # ── Media session boundary ────────────────────────────
                        # Log the end of the previous session before bumping generation
                        _prev_title = self.state_data.get("cleaned_title") or self.state_data.get("title", "?")
                        self.log(f"[MEDIA] Session {self.media_generation} ended: {_prev_title}")

                        # Prevent AniList/rewatch state from leaking across media.
                        # _rewatch_generation=-1 immediately invalidates any in-flight
                        # async writers that complete after this point.
                        self.state_data["watch_mode"] = "NORMAL"
                        self.state_data["rewatch_number"] = 0
                        self.state_data["possible_rewatch"] = False
                        self.state_data["rewatch_starting"] = False
                        self.state_data["_rewatch_generation"] = -1
                        self.state_data["anilist_identity"] = None
                        self.state_data["anilist_identity_state"] = "UNKNOWN"
                        self.current_anilist_identity = None

                        # Bump generation so DiscordManager and metadata workers
                        # drop any results from the previous session.
                        self.media_generation += 1
                        self.log(f"[MEDIA] Session {self.media_generation} started: {cleaned_title} {episode_str}")
                        self.log(f"[REWATCH] State reset for session {self.media_generation}")








                        last_track_key = track_key


                        if playback_state in ["playing", "paused"]:


                            self.state_data["episode_str"] = episode_str


                            cache_key = self._build_cache_key(
                                media_type, cleaned_title, episode_str,
                                artist=self.state_data.get('artist', '') if is_music else ''
                            )





                            if cache_key in self.metadata_cache:


                                cached_metadata = self.prepare_metadata_cover(self.metadata_cache.get(cache_key))


                                if cached_metadata and cached_metadata.get("image_url"):


                                    self.metadata_cache[cache_key] = cached_metadata


                                    self.state_data["metadata"] = cached_metadata


                                    self.state_data["local_image_path"] = cached_metadata.get("image_url")


                                    self.state_data["status_message"] = "Metadata loaded from cache."


                                    self.log(f"Playing '{cleaned_title}' (Metadata from cache)")


                                else:


                                    self.metadata_cache.pop(cache_key, None)


                                    self.save_metadata_cache()


                                    self.state_data["metadata"] = None


                                    self.state_data["local_image_path"] = None


                                    self.state_data["status_message"] = "Refreshing bad metadata cache..."


                                    self.log(f"Playing '{cleaned_title}' (Refreshing bad metadata cache...)")


                                    fetch_args = (cache_key, cleaned_title, episode_str, is_music, self.state_data["artist"], art_identity, media_type)


                                    threading.Thread(target=self._fetch_metadata_bg, args=fetch_args, daemon=True).start()


                            else:

                                # Check for a non-expired negative cache marker before spawning
                                _neg_entry = self.metadata_cache.get(cache_key)
                                _is_neg = isinstance(_neg_entry, dict) and _neg_entry.get('_negative')
                                _neg_expired = self._is_negative_expired(_neg_entry) if _is_neg else True

                                _dyn_neg = self._metadata_neg_cache.get(cache_key)
                                _dyn_is_neg = False
                                if _dyn_neg:
                                    _dyn_fail_time, _dyn_fail_count = _dyn_neg
                                    _dyn_cooldown = min(60 * (2 ** (_dyn_fail_count - 1)), 1800)
                                    if time.time() - _dyn_fail_time < _dyn_cooldown:
                                        _dyn_is_neg = True
                                    else:
                                        del self._metadata_neg_cache[cache_key]

                                if (_is_neg and not _neg_expired) or _dyn_is_neg:
                                    # All providers failed recently; wait for the TTL to expire
                                    if not getattr(self, "_last_neg_cache_log", None) == cache_key:
                                        self.log(f"[Metadata] Skipping fetch for '{cleaned_title}' — negative cache active")
                                        self._last_neg_cache_log = cache_key
                                    self.state_data["metadata"] = None
                                    self.state_data["local_image_path"] = None
                                    self.state_data["status_message"] = "No metadata found."
                                else:
                                    self.state_data["metadata"] = None


                                    self.state_data["local_image_path"] = None


                                    self.state_data["status_message"] = "Fetching metadata..."


                                    self.log(f"Playing '{cleaned_title}' (Fetching metadata...)")


                                    fetch_args = (cache_key, cleaned_title, episode_str, is_music, self.state_data["artist"], art_identity, media_type)


                                    threading.Thread(target=self._fetch_metadata_bg, args=fetch_args, daemon=True).start()


                        else:


                            self.state_data["metadata"] = None


                            self.state_data["episode_str"] = ""


                            self.state_data["local_image_path"] = None


                            self.state_data["local_arturl"] = ""


                            self.log("VLC stopped playback.")


                else:


                    self.state_data["vlc_connected"] = False


                    self.state_data["playback_state"] = "stopped"


                    self.state_data["title"] = ""


                    self.state_data["cleaned_title"] = ""


                    self.state_data["episode_str"] = ""


                    self.state_data["metadata"] = None


                    self.state_data["local_image_path"] = None


                    self.state_data["local_arturl"] = ""


                    self.state_data["_last_art_key"] = ""


                    self.state_data["_last_art_uri"] = ""


                    self.state_data["scene_snapshot_url"] = ""





            except requests.exceptions.RequestException:


                if self.state_data.get("vlc_connected"):


                    self.log("VLC connection lost.")
                    self._set_health("vlc", "DISCONNECTED")


                # VLC is unreachable — mark disconnected and hibernate briefly


                self.state_data["vlc_connected"] = False


                self.state_data["playback_state"] = "stopped"


                self.state_data["title"] = ""


                self.state_data["cleaned_title"] = ""


                self.state_data["episode_str"] = ""


                self.state_data["metadata"] = None


                self.state_data["local_image_path"] = None


                self.state_data["local_arturl"] = ""


                self.state_data["_last_art_key"] = ""


                self.state_data["_last_art_uri"] = ""


                self.state_data["scene_snapshot_url"] = ""


                self.discord_manager.clear_activity(self.media_generation)
                time.sleep(5)
                continue


            except Exception as e:


                if self.state_data.get("vlc_connected"):


                    self.log(f"VLC error: {e}")
                    self._set_health("vlc", "DISCONNECTED")


                self.state_data["vlc_connected"] = False


                self.state_data["playback_state"] = "stopped"


                self.state_data["title"] = ""


                self.state_data["cleaned_title"] = ""


                self.state_data["episode_str"] = ""


                self.state_data["metadata"] = None


                self.state_data["local_image_path"] = None


                self.state_data["local_arturl"] = ""


                self.state_data["_last_art_key"] = ""


                self.state_data["_last_art_uri"] = ""


                self.state_data["scene_snapshot_url"] = ""


                self.discord_manager.clear_activity(self.media_generation)
                continue





            desired_client_id = self.config.get("client_id", "").strip() or DEFAULT_CLIENT_ID

            if not getattr(self, 'rpc_enabled', True) or not self.state_data.get("vlc_connected") or self.state_data.get("playback_state") not in ["playing", "paused"]:
                self.discord_manager.clear_activity(self.media_generation)
            else:
                try:
                    kwargs = {}
                    media_type = self.state_data.get("media_type", "movie")

                    # Contextual Discord Activity Mapping
                    _meta = self.state_data.get("metadata") or {}
                    display_title = _meta.get("official_title") or self.state_data.get("cleaned_title") or self.state_data.get("title", "")
                    
                    if media_type == "music":
                        kwargs["activity_type"] = ActivityType.LISTENING
                        kwargs["details"] = display_title
                        kwargs["state"] = f"by {self.state_data.get('artist', 'Unknown')}"
                        kwargs["large_text"] = f"Album: {self.state_data.get('album', 'Unknown')}"
                    elif media_type == "movie":
                        kwargs["activity_type"] = ActivityType.WATCHING
                        kwargs["details"] = display_title
                        genres = _meta.get("genres", [])
                        if isinstance(genres, list):
                            genres = [g for g in genres if g.lower() not in ("anime", "animation")]
                            genre_str = ", ".join(genres[:3])
                        else:
                            genre_str = str(genres)
                        rating = _meta.get("rating") or _meta.get("imdb_rating") or ""
                        if rating:
                            try:
                                rating = str(round(float(rating), 1))
                            except (ValueError, TypeError):
                                rating = str(rating)
                        if rating and genre_str:
                            kwargs["state"] = f"{genre_str} | ⭐ {rating}"
                        elif genre_str:
                            kwargs["state"] = f"Genres: {genre_str}"
                        elif rating:
                            kwargs["state"] = f"⭐ {rating}"
                        desc = self.state_data.get("metadata", {}).get("description", "") if self.state_data.get("metadata") else ""
                        kwargs["large_text"] = display_title + (f" • {desc}" if desc else "")
                    else:
                        kwargs["activity_type"] = ActivityType.WATCHING
                        watch_mode = self.state_data.get("watch_mode", "NORMAL")
                        # Generation guard: ignore stale rewatch state from previous session
                        if self.state_data.get("_rewatch_generation", -1) != self.media_generation:
                            watch_mode = "NORMAL"
                        kwargs["details"] = f"\u21bb Rewatching {display_title}" if watch_mode == "REWATCH" else display_title

                        ep_str = self.state_data.get("episode_str", "")
                        _meta = self.state_data.get("metadata") or {}
                        rating = _meta.get("episode_rating") or _meta.get("rating") or _meta.get("imdb_rating") or ""
                        if rating:
                            try:
                                rating = str(round(float(rating), 1))
                            except (ValueError, TypeError):
                                rating = str(rating)
                        rating_str = f" | ⭐ {rating}" if rating else ""
                        if watch_mode == "REWATCH":
                            _rw_num = self.state_data.get("rewatch_number", 1) if self.state_data.get("_rewatch_generation", -1) == self.media_generation else 1
                            state_str = f"{ep_str} | Rewatch #{_rw_num}{rating_str}"
                        else:
                            state_str = f"{ep_str}{rating_str}"
                        if self.state_data.get("playback_state") == "paused":
                            kwargs["state"] = f"Paused | {state_str}" if state_str else "Paused"
                        else:
                            kwargs["state"] = state_str
                        
                        genres = _meta.get("genres", [])
                        if isinstance(genres, list):
                            genres = [g for g in genres if g.lower() not in ("anime", "animation")]
                            genre_str = ", ".join(genres[:3])
                        else:
                            genre_str = ""
                        kwargs["large_text"] = self.state_data.get("cleaned_title", self.state_data.get("title", "")) + (f" • {genre_str}" if genre_str else "")

                    # Assets
                    if self.state_data.get("metadata") and self.state_data["metadata"].get("image_url"):
                        kwargs["large_image"] = ensure_https(self.state_data["metadata"]["image_url"])
                    else:
                        kwargs["large_image"] = self.config.get("large_image_key", "vlc")
                    
                    snapshot_url = self.state_data.get("scene_snapshot_url", "")
                    if self.config.get("scene_snapshots") and snapshot_url:
                        kwargs["large_image"] = snapshot_url

                    play_key = self.config.get("small_image_key", "play")
                    pause_key = self.config.get("small_image_paused_key", "pause")
                    if play_key == "play": play_key = "https://iili.io/C2mXIp4.png"
                    if pause_key == "pause": pause_key = "https://iili.io/C2mXAj2.png"

                    if self.state_data.get("playback_state") == "playing":
                        kwargs["small_image"] = play_key
                        kwargs["small_text"] = "Playing"
                        if self.state_data.get("time", 0) > 0:
                            kwargs["start"] = int(time.time()) - self.state_data["time"]
                    else:
                        kwargs["small_image"] = pause_key
                        kwargs["small_text"] = "Paused"

                    if self.state_data.get("playback_state") == "playing" and self.state_data.get("length", 0) > 0:
                        current_time = int(time.time())
                        kwargs["start"] = current_time - self.state_data["time"]
                        kwargs["end"] = kwargs["start"] + self.state_data["length"]

                    buttons = []
                    _btn_meta = self.state_data.get("metadata") or {}
                    display_title = self.state_data.get("cleaned_title") or self.state_data.get("title", "")

                    if media_type != "music" and display_title:
                        trailer_query = urllib.parse.quote(f"{display_title} official trailer")
                        buttons.append({
                            "label": "Watch Trailer",
                            "url": f"https://www.youtube.com/results?search_query={trailer_query}"
                        })

                    anilist_username = self.fetch_anilist_username()
                    if anilist_username:
                        buttons.append({
                            "label": "My AniList Profile",
                            "url": f"https://anilist.co/user/{urllib.parse.quote(anilist_username)}/"
                        })
                    else:
                        anilist_id = _btn_meta.get("anilistId")
                        if media_type == "anime" and anilist_id:
                            buttons.append({"label": "View on AniList", "url": f"https://anilist.co/anime/{anilist_id}"})
                        elif media_type == "movie" and _btn_meta.get("page_url"):
                            buttons.append({"label": "View on IMDb", "url": _btn_meta["page_url"]})
                        elif media_type == "tv_show" and _btn_meta.get("page_url"):
                            buttons.append({"label": "View on TVmaze", "url": _btn_meta["page_url"]})

                    if buttons:
                        kwargs["buttons"] = buttons

                    self.discord_manager.submit_activity(self.media_generation, desired_client_id, kwargs)
                except Exception as e:
                    self.log(f"Error computing Discord activity: {e}")

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


                episode_rating = None


                matched_ep = None


                


                if embed and data.get("_embedded", {}).get("episodes"):


                    episodes = data["_embedded"]["episodes"]


                    if season_num is not None and episode_num is not None:


                        matched_ep = next((ep for ep in episodes if ep.get("season") == season_num and ep.get("number") == episode_num), None)


                        if not matched_ep and episode_num <= len(episodes):


                            matched_ep = episodes[episode_num - 1]


                    elif episode_num is not None:


                        matched_ep = next((ep for ep in episodes if ep.get("number") == episode_num), None)


                        if not matched_ep and episode_num <= len(episodes):


                            matched_ep = episodes[episode_num - 1]


                    


                    if matched_ep and matched_ep.get("rating"):


                        episode_rating = matched_ep["rating"].get("average")


                    if matched_ep and matched_ep.get("image"):


                        ep_img = matched_ep["image"].get("original") or matched_ep["image"].get("medium")


                        if ep_img:


                            img_url = ep_img


                


                return {


                    "image_url": img_url,


                    "rating": episode_rating or rating,


                    "episode_rating": episode_rating,


                    "show_rating": rating,


                    "rating_scope": "episode" if episode_rating else "show",


                    "genres": data.get("genres", []),


                    "description": f"TV Show | {data.get('type', '')}",


                    "page_url": data.get("url"),


                    "official_title": data.get("name"),


                    "total_episodes": len(episodes) if (embed and data.get("_embedded", {}).get("episodes")) else 0


                }


        except Exception:


            pass


        return None





    def fetch_jikan_metadata(self, title):


        try:


            # First try exact title


            url = f"https://api.jikan.moe/v4/anime?q={urllib.parse.quote(title)}&limit=1"


            r = requests.get(url, timeout=5)


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


                        "official_title": anime.get("title_english") or anime.get("title"),


                        "total_episodes": anime.get("episodes", 0)


                    }


            # Retry with first 3 words of title (helps with long titles like "Re:ZERO - Starting...")


            short = ' '.join(title.split()[:3])


            if short != title:


                url2 = f"https://api.jikan.moe/v4/anime?q={urllib.parse.quote(short)}&limit=5"


                r2 = requests.get(url2, timeout=5)


                if r2.status_code == 200:


                    data2 = r2.json()


                    results2 = data2.get("data", [])


                    for anime in results2:


                        img_url = None


                        if anime.get("images") and anime["images"].get("jpg"):


                            img_url = anime["images"]["jpg"].get("large_image_url")


                        if img_url:


                            return {


                                "image_url": img_url,


                                "rating": anime.get("score"),


                                "genres": [g.get("name") for g in anime.get("genres", []) if g.get("name")],


                                "description": f"Anime | {anime.get('type', '')}",


                                "page_url": anime.get("url"),


                                "official_title": anime.get("title_english") or anime.get("title"),


                                "total_episodes": anime.get("episodes", 0)


                            }


        except Exception:


            pass


        return None





    def fetch_anilist_metadata(self, title):


        """Fetch anime metadata from AniList (free GraphQL API, no auth, best English title matching)."""


        try:


            query = """


            query ($search: String) {


              Media(search: $search, type: ANIME) {


                id title { romaji english }


                coverImage { extraLarge large }


                averageScore genres siteUrl episodes


              }


            }


            """


            r = requests.post(


                "https://graphql.anilist.co",


                json={"query": query, "variables": {"search": title}},


                headers={"Content-Type": "application/json"},


                timeout=8


            )


            if r.status_code == 200:


                media = r.json().get("data", {}).get("Media")


                if media:


                    img = media.get("coverImage", {})


                    img_url = img.get("extraLarge") or img.get("large")


                    score = media.get("averageScore")


                    t = media.get("title", {})


                    official = t.get("english") or t.get("romaji")


                    return {


                        "image_url": img_url,


                        "rating": round(score / 10, 1) if score else None,


                        "genres": media.get("genres", []),


                        "description": f"Anime | {', '.join(media.get('genres', [])[:2])}",


                        "page_url": media.get("siteUrl"),


                        "anilistId": media.get("id"),


                        "official_title": official,


                        "total_episodes": media.get("episodes", 0)


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


                        "plot": plot,


                        "official_title": data.get("Title")


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


        self._backend = backend_instance


        


    def get_state(self):
        # Return a shallow copy so pywebview serialization is never racing
        # against the rpc_worker thread mutating state_data concurrently.
        return dict(self._backend.state_data)



    def get_config(self):


        return self._backend.config


    def toggle_rpc(self):


        self._backend.rpc_enabled = not getattr(self._backend, 'rpc_enabled', True)


        if not self._backend.rpc_enabled:


            self._backend.log("Discord Rich Presence temporarily disabled by user.")


        else:


            self._backend.log("Discord Rich Presence re-enabled.")


            self._backend._last_rpc_cleared = False


        return self._backend.rpc_enabled

    def manual_start_rewatch(self):
        queued = self._backend.start_anilist_rewatch()
        return {"success": queued, "error": "Rewatch start is already in progress." if not queued else ""}





    def get_stats(self):


        stats = {


            "total_watch_time": 0,


            "media_types": {"anime": 0, "movie": 0, "tv_show": 0, "music": 0},


            "recent_activity": [0] * 7,


            "history": [],


            "avg_session_minutes": 0,


            "binge_day": "--",


            "binge_hours": 0


        }


        try:


            db_path = getattr(self._backend, 'db_path', None)


            if not db_path or not os.path.exists(db_path):


                return stats


            conn = sqlite3.connect(db_path)


            c = conn.cursor()





            # Total watch time


            c.execute("SELECT SUM(watch_duration) FROM history")


            row = c.fetchone()


            stats["total_watch_time"] = int(row[0] or 0)





            # Media type breakdown using is_music flag


            c.execute("SELECT is_music, SUM(watch_duration) FROM history GROUP BY is_music")


            for is_music, dur in c.fetchall():


                dur = int(dur or 0)


                if is_music:


                    stats["media_types"]["music"] += dur


                else:


                    stats["media_types"]["anime"] += dur  # default non-music to anime bucket





            # 7-day activity (minutes)


            now = datetime.datetime.now()


            for i in range(7):


                day = now - datetime.timedelta(days=6 - i)


                day_str = day.strftime("%Y-%m-%d")


                c.execute("SELECT SUM(watch_duration) FROM history WHERE timestamp LIKE ?", (day_str + "%",))


                r = c.fetchone()


                stats["recent_activity"][i] = round((r[0] or 0) / 3600, 1)





            # Average session length (minutes)


            c.execute("SELECT COUNT(*) FROM history WHERE watch_duration > 0")


            total_sessions = c.fetchone()[0] or 1


            if total_sessions > 0 and stats["total_watch_time"] > 0:


                stats["avg_session_minutes"] = round((stats["total_watch_time"] / total_sessions) / 60, 1)





            # Most Binge-Watched Day


            c.execute("SELECT substr(timestamp, 1, 10) as day, SUM(watch_duration) as dur FROM history GROUP BY day ORDER BY dur DESC LIMIT 1")


            binge_res = c.fetchone()


            if binge_res and binge_res[1]:


                stats["binge_day"] = binge_res[0]


                stats["binge_hours"] = round(binge_res[1] / 3600, 1)





            # Recent history list (last 50 entries)


            c.execute("SELECT title, episode_str, is_music, watch_duration, timestamp FROM history ORDER BY id DESC LIMIT 50")


            for row in c.fetchall():


                stats["history"].append({


                    "title": row[0],


                    "episode": row[1],


                    "is_music": bool(row[2]),


                    "duration": int(row[3]),


                    "timestamp": row[4]


                })





            conn.close()


        except Exception as e:


            pass


            self._backend.log(f"Stats Error: {e}")


        return stats





        


    def save_config(self, new_config):


        try:


            self._backend.config.update(new_config)


            save_config(self._backend.config)


            return {"success": True}


        except Exception as e:


            return {"success": False, "error": str(e)}


            


    def open_url(self, url):


        import webbrowser


        webbrowser.open(url)


        return {"success": True}


        


    def sync_discord_widget(self):


        threading.Thread(target=self._backend.force_sync_widget, daemon=True).start()


        threading.Thread(target=self._backend.force_sync_widget_v2, daemon=True).start()


        return {"success": True}


            


    def force_update(self):


        """Force Sync button: clears stuck cover, resets metadata, and re-triggers RPC update."""


        b = self._backend


        # 1. Clear current metadata so the cover re-fetches


        b.state_data["metadata"] = None


        b.state_data["local_image_path"] = None


        b.state_data["local_arturl"] = ""


        b.state_data["_last_art_key"] = ""


        b.state_data["_last_art_uri"] = ""


        # 2. Clear the metadata cache entry for this track so it re-fetches fresh


        title = b.state_data.get("cleaned_title", "")


        ep_str = b.state_data.get("episode_str", "")


        media_type = b.state_data.get("media_type", "movie")


        artist = b.state_data.get("artist", "")


        cache_key = f"{media_type}:{title}:{artist}" if media_type == "music" else f"{media_type}:{title}:{ep_str}"


        if cache_key in b.metadata_cache:


            del b.metadata_cache[cache_key]


            b.save_metadata_cache()


        # 3. Clear the scrobbled memory so AniList re-checks this episode


        identity = b.current_anilist_identity or {}
        media_id = identity.get("anilist_id")
        if media_id:
            episode_key = f"{media_id}:E"
            b.scrobbled_episodes = {k for k in b.scrobbled_episodes if not k.startswith(episode_key)}
            b.refresh_anilist_media_list(media_id)
        else:
            # Preserve compatibility for any pre-v5.2 in-memory keys.
            episode_key = f"{title}:E"
            b.scrobbled_episodes = {k for k in b.scrobbled_episodes if not k.startswith(episode_key)}


        # 4. Signal the worker to reset track key so it re-pushes RPC


        b.force_update_flag = True


        return {"success": True}





    def get_anilist_logs(self):


        """Return the in-memory AniList log lines for the Logs tab."""


        return {"success": True, "logs": list(self._backend.anilist_logs)}





    def auth_anilist(self):


        """Launch AniList OAuth2 implicit flow. Token captured via local HTTP server."""


        threading.Thread(target=self._backend.start_anilist_oauth, daemon=True).start()


        return {"success": True}





    def manual_check_for_updates(self):


        """Triggered by Check for Updates button on frontend."""


        def _check():


            try:


                api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


                headers = {


                    "User-Agent": f"VLC-RPC/{CURRENT_VERSION}",


                    "Accept": "application/vnd.github+json"


                }


                r = requests.get(api_url, headers=headers, timeout=8)


                if r.status_code != 200:


                    return {"update_available": False, "current_version": CURRENT_VERSION}





                data = r.json()


                latest_tag = data.get("tag_name", "").lstrip("v")


                if not latest_tag:


                    return {"update_available": False, "current_version": CURRENT_VERSION}


                


                # Parse versions as tuples for reliable comparison


                def _parse(v):


                    try:


                        return tuple(int(x) for x in v.strip().split("."))


                    except Exception:


                        return (0,)





                if _parse(latest_tag) > _parse(CURRENT_VERSION):


                    download_url = data.get("html_url", "")


                    for asset in data.get("assets", []):


                        name = asset.get("name", "").lower()


                        if name.endswith(".exe") and "setup" in name:


                            download_url = asset.get("browser_download_url", download_url)


                            break


                    changelog = data.get("body", "").strip()


                    if len(changelog) > 400:


                        changelog = changelog[:397] + "..."


                    


                    self._backend.state_data["update_available"] = True


                    self._backend.state_data["update_version"] = latest_tag


                    self._backend.state_data["update_download_url"] = download_url


                    self._backend.state_data["update_changelog"] = changelog


                    show_toast("Update Available", f"v{latest_tag} is available! Click Update in the app.")


                    return {


                        "update_available": True,


                        "current_version": CURRENT_VERSION,


                        "update_version": latest_tag,


                        "update_changelog": changelog


                    }


                else:


                    return {"update_available": False, "current_version": CURRENT_VERSION}


            except Exception as e:


                return {"update_available": False, "current_version": CURRENT_VERSION, "error": str(e)}





        import concurrent.futures


        with concurrent.futures.ThreadPoolExecutor() as executor:


            future = executor.submit(_check)


            res = future.result()


        return res





    def trigger_download_update(self):


        """Start downloading the update in a background thread."""


        download_url = self._backend.state_data.get("update_download_url")


        if not download_url:


            return {"success": False, "error": "No download URL found."}





        self._backend.state_data["update_status"] = "downloading"


        self._backend.state_data["update_progress"] = 0


        


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


                                self._backend.state_data["update_progress"] = int((downloaded_size / total_size) * 100)


                


                self._backend.state_data["update_temp_exe"] = temp_exe


                self._backend.state_data["update_status"] = "ready"


                self._backend.state_data["update_progress"] = 100


            except Exception as e:


                pass


                self._backend.state_data["update_status"] = "error"





        threading.Thread(target=_download_task, daemon=True).start()


        return {"success": True}





    def install_update(self):


        """Launch the downloaded silent installer and kill this app."""


        temp_exe = self._backend.state_data.get("update_temp_exe")


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


        threading.Thread(target=self._backend.start_discord_oauth, daemon=True).start()


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


            b = self._backend


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
        backend.discord_manager.stop()


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


            pass


    def is_minimize_to_tray(item):


        return backend.config.get('minimize_to_tray', True)


        


    def toggle_minimize_to_tray(icon, item):


        backend.config['minimize_to_tray'] = not backend.config.get('minimize_to_tray', True)


        save_config(backend.config)


        


    def on_quit(icon, item):


        backend.state_data["exit_flag"] = True
        backend.discord_manager.stop()


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
    backend.discord_manager.stop()


    os._exit(0)
