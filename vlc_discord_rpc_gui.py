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
    "small_image_paused_text": "Paused"
}

def clean_title(title):
    # Try using guessit for intelligent media parsing
    if guessit:
        try:
            guessed = guessit.guessit(title)
            cleaned = guessed.get('title', title)
            
            episode_str = ""
            if guessed.get('type') == 'movie':
                if guessed.get('year'):
                    cleaned = f"{cleaned} ({guessed.get('year')})"
            elif guessed.get('type') == 'episode':
                season = guessed.get('season')
                episode = guessed.get('episode')
                if season and episode:
                    if isinstance(season, list): season = season[0]
                    if isinstance(episode, list): episode = episode[0]
                    episode_str = f"Season {season} Episode {episode}"
                elif episode:
                    if isinstance(episode, list): episode = episode[0]
                    episode_str = f"Episode {episode}"
            
            # Simple title casing
            if cleaned and isinstance(cleaned, str):
                cleaned = ' '.join(word.capitalize() for word in str(cleaned).split())
                
            return str(cleaned), episode_str
        except Exception:
            pass

    # Fallback to standard regex parsing if guessit fails or is not installed
    title = re.sub(r'\[[^\]]*\]', '', title)
    title = re.sub(r'\([^\)]*\)', '', title)
    
    episode_str = ""
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

    words_to_remove = [
        r'\b1080p\b', r'\b720p\b', r'\b480p\b', r'\b2160p\b', r'\b4k\b',
        r'\bbluray\b', r'\bwebrip\b', r'\bweb-dl\b', r'\bdvdrip\b',
        r'\bx264\b', r'\bx265\b', r'\bh264\b', r'\bhevc\b',
        r'\bdual[- ]audio\b', r'\bmulti\b', r'\beng\b', r'\bsub\b', r'\bdub\b',
        r'\byify\b', r'\bxvid\b'
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
        self.state_data = {
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
            "exit_flag": False
        }
        self.force_update_flag = False
        self.window = None
        self.stop_event = threading.Event()
        self.current_watch_duration = 0
        self.setup_database()
        self.metadata_cache = self.load_metadata_cache()
        self.worker_thread = threading.Thread(target=self.rpc_worker, daemon=True)
        self.worker_thread.start()

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
            se_parsed = re.search(r'Season\s+(\d+)\s+Episode\s+(\d+)', episode_str)
            if se_parsed:
                season_num = int(se_parsed.group(1))
                episode_num = int(se_parsed.group(2))
            else:
                ep_parsed = re.search(r'Episode\s+(\d+)', episode_str)
                if ep_parsed:
                    episode_num = int(ep_parsed.group(1))

            metadata = None
            if is_music:
                metadata = self.fetch_itunes_metadata(cleaned_title, artist)
            else:
                metadata = self.fetch_tvmaze_metadata(cleaned_title, season_num=season_num, episode_num=episode_num)
                if not metadata or not metadata.get("image_url"):
                    metadata = self.fetch_jikan_metadata(cleaned_title)
                if not metadata or not metadata.get("image_url"):
                    metadata = self.fetch_wikipedia_metadata(cleaned_title)

            if metadata:
                if metadata.get("image_url"):
                    color = self.get_dominant_color(metadata["image_url"])
                    if color:
                        metadata["dominant_color"] = color
                self.metadata_cache[cache_key] = metadata
                self.save_metadata_cache()

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
                    raw_title = meta.get("title") or meta.get("filename") or "Unknown Track"
                    # Strip common media file extensions
                    raw_title = re.sub(r'\.(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', raw_title, flags=re.I)
                    self.state_data["title"] = raw_title.strip()
                    self.state_data["artist"] = meta.get("artist", "")
                    self.state_data["album"] = meta.get("album", "")
                    if not meta and playback_state == "playing":
                        self.state_data["title"] = "Streaming Audio/Video"
                        
                    if playback_state == "playing":
                        self.current_watch_duration += self.config.get("update_interval", 2)
                        
                    cleaned_title, episode_str = clean_title(self.state_data["title"])
                    is_music = is_music_file(self.state_data["title"], self.state_data["artist"], self.state_data["album"])
                    self.state_data["is_music"] = is_music
                    self.state_data["cleaned_title"] = cleaned_title
                    track_key = f"{self.state_data['title']}:{self.state_data['artist']}"
                    
                    if self.force_update_flag:
                        last_track_key = None
                        self.force_update_flag = False
                    
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
                            cache_key = f"music:{cleaned_title}:{self.state_data['artist']}" if is_music else f"video:{cleaned_title}:{episode_str}"
                            
                            if cache_key in self.metadata_cache:
                                self.state_data["metadata"] = self.metadata_cache[cache_key]
                                self.state_data["local_image_path"] = self.state_data["metadata"].get("image_url")
                                self.state_data["status_message"] = "Metadata loaded from cache."
                            else:
                                # Clear old metadata immediately so UI updates fast
                                self.state_data["metadata"] = None
                                self.state_data["local_image_path"] = None
                                self.state_data["status_message"] = "Fetching metadata..."
                                # Fetch in background thread so we don't block VLC polling
                                fetch_args = (cache_key, cleaned_title, episode_str, is_music, self.state_data["artist"])
                                threading.Thread(target=self._fetch_metadata_bg, args=fetch_args, daemon=True).start()
                        else:
                            self.state_data["metadata"] = None
                            self.state_data["episode_str"] = ""
                            self.state_data["local_image_path"] = None
                else:
                    self.state_data["vlc_connected"] = False
            except Exception as e:
                self.state_data["vlc_connected"] = False
                
            desired_client_id = self.config.get("client_id", "").strip() or DEFAULT_CLIENT_ID
            
            if rpc and current_client_id != desired_client_id:
                try:
                    rpc.close()
                except Exception:
                    pass
                rpc = None
                self.state_data["rpc_connected"] = False

            if not rpc:
                try:
                    rpc = Presence(desired_client_id)
                    rpc.connect()
                    current_client_id = desired_client_id
                    self.state_data["rpc_connected"] = True
                    self.state_data["status_message"] = f"Connected to Discord."
                except Exception as e:
                    rpc = None
                    current_client_id = None
                    self.state_data["rpc_connected"] = False
                    self.state_data["status_message"] = f"Discord connection failed."

            if rpc and self.state_data["rpc_connected"]:
                if not self.state_data["vlc_connected"] or self.state_data["playback_state"] not in ["playing", "paused"]:
                    try:
                        rpc.clear()
                    except Exception:
                        pass
                else:
                    try:
                        kwargs = {}
                        act_type = ActivityType.LISTENING if is_music else ActivityType.WATCHING
                        kwargs["activity_type"] = act_type
                        
                        kwargs["details"] = self.state_data.get("cleaned_title", self.state_data["title"])
                        
                        if not is_music and self.state_data["episode_str"]:
                            # Format state as "Season X, Episode Y"
                            ep_str = self.state_data["episode_str"].replace("Episode", ", Episode") if "Season" in self.state_data["episode_str"] else self.state_data["episode_str"]
                            
                            # Smart State Messages
                            if self.current_watch_duration > 7200:
                                state_msg = f"Marathon 🍿 • {ep_str}"
                            elif self.current_watch_duration > 3600:
                                state_msg = f"Binge Mode 🔥 • {ep_str}"
                            else:
                                state_msg = ep_str
                                
                            if self.state_data["playback_state"] == "paused":
                                kwargs["state"] = f"Paused | {ep_str}"
                            else:
                                kwargs["state"] = state_msg
                                
                            # Episode Progress as Party Size
                            ep_num = 0
                            m = re.search(r'Episode\s*(\d+)', self.state_data["episode_str"], re.I)
                            if m:
                                ep_num = int(m.group(1))
                                
                            total_ep = self.state_data["metadata"].get("total_episodes") if self.state_data["metadata"] else 0
                            if not total_ep or total_ep < ep_num:
                                total_ep = ep_num
                                
                            if ep_num > 0 and total_ep > 0:
                                kwargs["party_id"] = "vlc_party_" + hashlib.md5(self.state_data.get("cleaned_title", "").encode()).hexdigest()
                                kwargs["party_size"] = [ep_num, total_ep]
                            
                            # Generate short string like S4E2
                            short_ep = ""
                            m = re.search(r'Season\s*(\d+).*?Episode\s*(\d+)', self.state_data["episode_str"], re.I)
                            if m:
                                short_ep = f"S{m.group(1)}E{m.group(2)}"
                            else:
                                m2 = re.search(r'Episode\s*(\d+)', self.state_data["episode_str"], re.I)
                                if m2:
                                    short_ep = f"Ep{m2.group(1)}"
                                    
                            # We put the short episode tag in the small image hover text so it shows up
                            small_txt = short_ep if short_ep else "Watching"
                        else:
                            if self.state_data["artist"]:
                                if self.state_data["playback_state"] == "paused":
                                    kwargs["state"] = f"Paused | {self.state_data['artist']}"
                                else:
                                    kwargs["state"] = self.state_data["artist"]
                            elif self.state_data["playback_state"] == "paused":
                                kwargs["state"] = "Paused"
                            # If no artist and playing, don't set state at all (Discord rejects empty strings)
                            small_txt = "Listening" if is_music else "Playing"
                            
                        # Assets
                        if self.state_data["metadata"] and self.state_data["metadata"].get("image_url"):
                            kwargs["large_image"] = self.state_data["metadata"]["image_url"]
                            if self.state_data["metadata"].get("description"):
                                kwargs["large_text"] = self.state_data.get("cleaned_title", self.state_data["title"]) + " • " + self.state_data["metadata"]["description"]
                            else:
                                kwargs["large_text"] = self.state_data.get("cleaned_title", self.state_data["title"])
                        else:
                            kwargs["large_image"] = self.config.get("large_image_key", "vlc")
                            kwargs["large_text"] = self.state_data.get("cleaned_title", self.state_data["title"])
                            
                        # Try to use configured keys, but fallback to direct URLs if using default non-existent keys
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

                        # Buttons
                        buttons = []
                        if self.state_data["metadata"] and self.state_data["metadata"].get("page_url"):
                            buttons.append({"label": "View Info", "url": self.state_data["metadata"]["page_url"]})
                        buttons.append({"label": "Watch Trailer" if not is_music else "Search Song", "url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(self.state_data['title'] + (' trailer' if not is_music else ''))}"})
                        kwargs["buttons"] = buttons

                        rpc.update(**kwargs)
                    except Exception as e:
                        self.state_data["rpc_connected"] = False
                        rpc = None
                        
            time.sleep(self.config.get("update_interval", 2))

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
    def __init__(self, backend):
        self.backend = backend
        
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
            
    def force_update(self):
        self.backend.force_update_flag = True
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


backend = RPCBackend()
api = WebApi(backend)

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
    
    # Clean up legacy startup file
    if os.path.exists(old_startup_path):
        try: os.remove(old_startup_path)
        except Exception: pass
    
    def is_startup_enabled(item):
        return os.path.exists(startup_path)
        
    def toggle_startup(icon, item):
        if is_startup_enabled(item):
            try:
                os.remove(startup_path)
            except Exception:
                pass
        else:
            try:
                if getattr(sys, 'frozen', False):
                    # PyInstaller bundle
                    python_exe = sys.executable
                    script_path = ""
                else:
                    python_exe = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                    if not os.path.exists(python_exe):
                        python_exe = sys.executable
                    script_path = os.path.abspath(__file__)
                
                working_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
                
                with open(startup_path, 'w') as f:
                    if script_path:
                        f.write(f'@echo off\ncd /d "{working_dir}"\nstart "" "{python_exe}" "{script_path}" --minimized\n')
                    else:
                        f.write(f'@echo off\ncd /d "{working_dir}"\nstart "" "{python_exe}" --minimized\n')
            except Exception:
                pass

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
    
    # Get correct path for PyInstaller
    if getattr(sys, 'frozen', False):
        web_path = os.path.join(sys._MEIPASS, 'web')
    else:
        web_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
    
    html_file = os.path.join(web_path, 'index.html')
    
    window = webview.create_window('VLC RPC', html_file, js_api=api, width=780, height=640, min_size=(600, 500))
    backend.set_window(window)
    
    window.events.closing += on_closing
    
    def on_loaded():
        if start_minimized:
            window.hide()
        # Start tray icon only after window is fully initialized to prevent COM deadlocks
        threading.Thread(target=setup_tray, daemon=True).start()
        
    window.events.loaded += on_loaded
    
    webview.start()
    backend.state_data["exit_flag"] = True
    os._exit(0)
