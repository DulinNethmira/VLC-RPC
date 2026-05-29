import os
import sys
import time
import json
import threading
import re
import urllib.parse
import hashlib
import requests
import asyncio
from pypresence import Presence, ActivityType
import webview
import pystray
from PIL import Image

CONFIG_FILE = "config.json"
CACHE_FILE = "metadata_cache.json"
COVERS_DIR = "covers_cache"
DEFAULT_CLIENT_ID = "1347834940380676156"

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
    title = os.path.splitext(title)[0]
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
        self.config = load_config()
        self.metadata_cache = self.load_metadata_cache()
        self.state_data = {
            "vlc_connected": False,
            "rpc_connected": False,
            "playback_state": "offline",
            "title": "",
            "artist": "",
            "album": "",
            "time": 0,
            "length": 0,
            "volume": 0,
            "status_message": "Starting...",
            "metadata": None,
            "episode_str": "",
            "local_image_path": None,
            "exit_flag": False
        }
        self.worker_thread = threading.Thread(target=self.rpc_worker, daemon=True)
        self.worker_thread.start()
        self.window = None

    def set_window(self, window):
        self.window = window
        self.ui_update_thread = threading.Thread(target=self.update_ui_loop, daemon=True)
        self.ui_update_thread.start()

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
                    self.state_data["title"] = meta.get("title") or meta.get("filename") or "Unknown Track"
                    self.state_data["artist"] = meta.get("artist", "")
                    self.state_data["album"] = meta.get("album", "")
                    if not meta and playback_state == "playing":
                        self.state_data["title"] = "Streaming Audio/Video"
                        
                    cleaned_title, episode_str = clean_title(self.state_data["title"])
                    is_music = is_music_file(self.state_data["title"], self.state_data["artist"], self.state_data["album"])
                    track_key = f"{playback_state}:{self.state_data['title']}:{self.state_data['artist']}"
                    
                    if track_key != last_track_key:
                        last_track_key = track_key
                        if playback_state in ["playing", "paused"]:
                            cache_key = f"music:{cleaned_title}:{self.state_data['artist']}" if is_music else f"video:{cleaned_title}:{episode_str}"
                            
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
                            if cache_key in self.metadata_cache:
                                metadata = self.metadata_cache[cache_key]
                            else:
                                if is_music:
                                    metadata = self.fetch_itunes_metadata(cleaned_title, self.state_data["artist"])
                                else:
                                    metadata = self.fetch_tvmaze_metadata(cleaned_title, season_num=season_num, episode_num=episode_num)
                                    if not metadata or not metadata.get("image_url"):
                                        metadata = self.fetch_jikan_metadata(cleaned_title)
                                    if not metadata or not metadata.get("image_url"):
                                        metadata = self.fetch_wikipedia_metadata(cleaned_title)
                                        
                                if metadata:
                                    self.metadata_cache[cache_key] = metadata
                                    self.save_metadata_cache()
                                    
                            self.state_data["metadata"] = metadata
                            self.state_data["episode_str"] = episode_str
                            self.state_data["local_image_path"] = metadata.get("image_url") if metadata else None
                            self.state_data["status_message"] = "Metadata loaded successfully."
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
                except (DiscordNotFound, DiscordError, Exception) as e:
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
                        kwargs["activity_type"] = act_type.value
                        
                        kwargs["details"] = self.state_data["title"]
                        
                        if not is_music and self.state_data["episode_str"]:
                            # Format state as "Season X, Episode Y"
                            ep_str = self.state_data["episode_str"].replace("Episode", ", Episode") if "Season" in self.state_data["episode_str"] else self.state_data["episode_str"]
                            
                            # Generate short string like S4E2
                            short_ep = ""
                            m = re.search(r'Season\s*(\d+).*?Episode\s*(\d+)', self.state_data["episode_str"], re.I)
                            if m:
                                short_ep = f"S{m.group(1)}E{m.group(2)}"
                            else:
                                m2 = re.search(r'Episode\s*(\d+)', self.state_data["episode_str"], re.I)
                                if m2:
                                    short_ep = f"Ep{m2.group(1)}"
                                    
                            if self.state_data["playback_state"] == "paused":
                                kwargs["state"] = f"Paused | {ep_str}"
                            else:
                                kwargs["state"] = ep_str
                                
                            # We put the short episode tag in the small image hover text so it shows up
                            small_txt = short_ep if short_ep else "Watching"
                        else:
                            kwargs["state"] = self.state_data["artist"] if self.state_data["artist"] else ("Paused" if self.state_data["playback_state"] == "paused" else "")
                            if self.state_data["playback_state"] == "paused" and self.state_data["artist"]:
                                kwargs["state"] = f"Paused | {self.state_data['artist']}"
                            small_txt = "Listening" if is_music else "Playing"
                            
                        # Assets
                        if self.state_data["metadata"] and self.state_data["metadata"].get("image_url"):
                            kwargs["large_image"] = self.state_data["metadata"]["image_url"]
                            if self.state_data["metadata"].get("description"):
                                kwargs["large_text"] = self.state_data["metadata"]["description"]
                        else:
                            kwargs["large_image"] = self.config.get("large_image_key", "vlc")
                            kwargs["large_text"] = self.config.get("large_image_text", "VLC Media Player")
                            
                        if self.state_data["playback_state"] == "playing":
                            kwargs["small_image"] = self.config.get("small_image_key", "play")
                            kwargs["small_text"] = small_txt
                        else:
                            kwargs["small_image"] = self.config.get("small_image_paused_key", "pause")
                            kwargs["small_text"] = "Paused"
                            
                        if self.state_data["playback_state"] == "playing" and self.state_data["length"] > 0:
                            current_time = int(time.time())
                            kwargs["start"] = current_time - self.state_data["time"]
                            kwargs["end"] = kwargs["start"] + self.state_data["length"]

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
                    "page_url": data.get("url")
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
                        "page_url": anime.get("url")
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

    def update_ui_loop(self):
        while not self.state_data["exit_flag"]:
            if self.window:
                try:
                    js_code = f"updateState({json.dumps(self.state_data)})"
                    self.window.evaluate_js(js_code)
                except Exception:
                    pass
            time.sleep(1)


class WebApi:
    def __init__(self, backend):
        self.backend = backend
        
    def get_config(self):
        return self.backend.config
        
    def save_config(self, new_config):
        try:
            self.backend.config.update(new_config)
            save_config(self.backend.config)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def force_update(self):
        pass # UI loop does this anyway


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
    startup_path = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup', 'VLC_Discord_RP.bat')
    
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
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
        
    image_path = os.path.join(application_path, "web", "icon.ico")
    if os.path.exists(image_path):
        image = Image.open(image_path)
    else:
        image = Image.new('RGB', (64, 64), color='black')
        
    menu = pystray.Menu(
        pystray.MenuItem('Open VLC Discord RP', on_show, default=True),
        pystray.MenuItem('Minimize to Tray', toggle_minimize_to_tray, checked=is_minimize_to_tray),
        pystray.MenuItem('Start with System', toggle_startup, checked=is_startup_enabled),
        pystray.MenuItem('Exit', on_quit)
    )
    icon = pystray.Icon("vlc_rpc", image, "VLC Discord RP", menu)
    icon.run()

if __name__ == '__main__':
    start_minimized = "--minimized" in sys.argv
    
    threading.Thread(target=setup_tray, daemon=True).start()
    
    # Get correct path for PyInstaller
    if getattr(sys, 'frozen', False):
        web_path = os.path.join(sys._MEIPASS, 'web')
    else:
        web_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
    
    html_file = os.path.join(web_path, 'index.html')
    
    window = webview.create_window('VLC Discord RP', html_file, js_api=api, width=780, height=640, min_size=(600, 500))
    backend.set_window(window)
    
    window.events.closing += on_closing
    
    if start_minimized:
        # Hide window immediately after starting
        def on_loaded():
            window.hide()
        window.events.loaded += on_loaded
    
    webview.start()
    backend.state_data["exit_flag"] = True
    os._exit(0)
