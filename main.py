import os
import sys
import time
import json
import threading
import re
import urllib.parse
import hashlib
import requests
import eel
import pystray
from PIL import Image
from requests.auth import HTTPBasicAuth
import asyncio
from pypresence import Presence, ActivityType
from pypresence.exceptions import DiscordNotFound, DiscordError

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
    # Remove file extension
    title = os.path.splitext(title)[0]
    
    # Remove bracketed/parenthesized tags (e.g. [1080p], [SubsPlease])
    title = re.sub(r'\[[^\]]*\]', '', title)
    title = re.sub(r'\([^\)]*\)', '', title)
    
    # Extract season and episode
    episode_str = ""
    # S01E10 or S1E10
    se_match = re.search(r'\bS(\d+)\s*E(\d+)\b', title, re.IGNORECASE)
    if se_match:
        episode_str = f"Season {int(se_match.group(1))} Episode {int(se_match.group(2))}"
        title = re.sub(r'\bS\d+\s*E\d+\b', '', title, flags=re.IGNORECASE)
    # Episode xx or Ep xx
    elif re.search(r'\b(?:Episode|Ep)\s*(\d+)\b', title, re.IGNORECASE):
        ep_match = re.search(r'\b(?:Episode|Ep)\s*(\d+)\b', title, re.IGNORECASE)
        episode_str = f"Episode {int(ep_match.group(1))}"
        title = re.sub(r'\b(?:Episode|Ep)\s*\d+\b', '', title, flags=re.IGNORECASE)
    # Dash + number (e.g. Bleach - 15)
    elif re.search(r'-\s*(\d+)\b', title):
        dash_match = re.search(r'-\s*(\d+)\b', title)
        episode_str = f"Episode {int(dash_match.group(1))}"
        title = re.sub(r'-\s*\d+\b', '', title)

    # Clean release group tags and common words
    words_to_remove = [
        r'\b1080p\b', r'\b720p\b', r'\b480p\b', r'\b2160p\b', r'\b4k\b',
        r'\bbluray\b', r'\bwebrip\b', r'\bweb-dl\b', r'\bdvdrip\b',
        r'\bx264\b', r'\bx265\b', r'\bh264\b', r'\bhevc\b',
        r'\bdual[- ]audio\b', r'\bmulti\b', r'\beng\b', r'\bsub\b', r'\bdub\b',
        r'\byify\b', r'\bxvid\b'
    ]
    for word in words_to_remove:
        title = re.sub(word, '', title, flags=re.IGNORECASE)
        
    # Clean multiple spaces/dashes/dots
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

class RPCBackend:
    def __init__(self):
        # Load Config & Cache
        self.config = load_config()
        self.metadata_cache = self.load_metadata_cache()
        self.last_image_path = None
        
        # Shared state
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
            "status_message": "Starting background worker...",
            "metadata": None,
            "episode_str": "",
            "local_image_path": None,
            "exit_flag": False
        }
        
        # Start worker thread
        self.worker_thread = threading.Thread(target=self.rpc_worker, daemon=True)
        self.worker_thread.start()
        

    def load_metadata_cache(self):
        if not os.path.exists(CACHE_FILE):
            return {}
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_metadata_cache(self):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self.metadata_cache, f, indent=4)
        except Exception:
            pass

    def draw_synthwave_header(self):
        self.canvas = tk.Canvas(self, width=680, height=120, bg="#0c0214", highlightthickness=0)
        self.canvas.pack(fill="x", side="top")
        
        # Draw sky
        self.canvas.create_rectangle(0, 0, 680, 120, fill="#0c0214", outline="")
        
        # Sun
        cx, cy, r = 340, 85, 45
        for y_offset in range(-r, r):
            y_curr = cy + y_offset
            gap_height = 4
            cycle = 14
            if y_curr > cy - 10:
                if (y_curr - cy) % cycle < gap_height:
                    continue
            dx = (r**2 - y_offset**2)**0.5
            ratio = (y_offset + r) / (r * 2)
            r_val = 255
            g_val = int(120 * (1 - ratio))
            b_val = int(200 * ratio)
            color_hex = f"#{r_val:02x}{g_val:02x}{b_val:02x}"
            self.canvas.create_line(cx - dx, y_curr, cx + dx, y_curr, fill=color_hex, width=1)
            
        # Horizon & Grid
        horizon_y = 90
        self.canvas.create_line(0, horizon_y, 680, horizon_y, fill="#ff00aa", width=2)
        
        vanish_x = 340
        for x_base in range(-680, 1360, 50):
            self.canvas.create_line(vanish_x, horizon_y, x_base, 120, fill="#ff00aa", width=1)
            
        for i in range(6):
            y = horizon_y + int((120 - horizon_y) * (1.6 ** i - 1) / (1.6 ** 5 - 1))
            self.canvas.create_line(0, y, 680, y, fill="#ff00aa", width=1)
            
        # Glitch Title
        self.canvas.create_text(342, 34, text="V L C   D I S C O R D   R P C", font=("Helvetica", 20, "bold"), fill="#ff00aa")
        self.canvas.create_text(340, 32, text="V L C   D I S C O R D   R P C", font=("Helvetica", 20, "bold"), fill="#00f0ff")
        self.canvas.create_text(341, 33, text="V L C   D I S C O R D   R P C", font=("Helvetica", 20, "bold"), fill="#ffffff")

    def on_closing(self):
        self.state_data["exit_flag"] = True
        self.destroy()

    def rpc_worker(self):
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception:
            pass
            
        rpc = None
        last_client_id = ""
        last_update_time = 0
        last_presence_payload = {}
        last_track_key = ""
        
        while not self.state_data["exit_flag"]:
            config = self.config
            pw = config.get("vlc_password", "")
            host = config.get("vlc_host", "localhost")
            port = config.get("vlc_port", 8080)
            
            client_id = config.get("client_id", DEFAULT_CLIENT_ID)
            if not client_id:
                client_id = DEFAULT_CLIENT_ID
                
            vlc_url = f"http://{host}:{port}/requests/status.json"
            
            if client_id != last_client_id and rpc is not None:
                try:
                    rpc.close()
                except Exception:
                    pass
                rpc = None
                self.state_data["rpc_connected"] = False
                last_presence_payload = {}
            last_client_id = client_id
            
            # Fetch VLC status
            vlc_connected = False
            playback_state = "offline"
            vlc_data = {}
            
            if pw:
                try:
                    response = requests.get(vlc_url, auth=HTTPBasicAuth('', pw), timeout=1.2)
                    if response.status_code == 200:
                        vlc_connected = True
                        vlc_data = response.json()
                        playback_state = vlc_data.get("state", "stopped")
                    elif response.status_code == 401:
                        playback_state = "auth_failed"
                except requests.exceptions.RequestException:
                    pass
            else:
                playback_state = "no_password"
                
            self.state_data["vlc_connected"] = vlc_connected
            self.state_data["playback_state"] = playback_state
            
            if vlc_connected:
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
                    
                # Clean title and fetch metadata if title changed
                track_key = f"{playback_state}:{self.state_data['title']}:{self.state_data['artist']}"
                if track_key != last_track_key:
                    last_track_key = track_key
                    
                    if playback_state in ["playing", "paused"]:
                        self.state_data["status_message"] = "Fetching metadata..."
                        cleaned_title, episode_str = clean_title(self.state_data["title"])
                        
                        is_music = is_music_file(self.state_data["title"], self.state_data["artist"], self.state_data["album"])
                        cache_key = f"music:{cleaned_title}:{self.state_data['artist']}" if is_music else f"video:{cleaned_title}:{episode_str}"
                        
                        # Parse season/episode numbers from episode_str
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
                                
                        local_image_path = None
                        if metadata and metadata.get("image_url"):
                            local_image_path = self.download_cover_image(metadata["image_url"])
                            
                        self.state_data["metadata"] = metadata
                        self.state_data["episode_str"] = episode_str
                        self.state_data["local_image_path"] = local_image_path
                        self.state_data["status_message"] = "Metadata loaded successfully."
                    else:
                        self.state_data["metadata"] = None
                        self.state_data["episode_str"] = ""
                        self.state_data["local_image_path"] = None
                        
            rpc_retry_count = 0
            if playback_state in ["playing", "paused"] and self.state_data["title"]:
                if rpc is None:
                    self.state_data["status_message"] = "Connecting to Discord RPC..."
                    try:
                        rpc = Presence(client_id)
                        rpc.connect()
                        self.state_data["rpc_connected"] = True
                        last_presence_payload = {}
                        rpc_retry_count = 0
                        if client_id == "1347834940380676156" or client_id == "963617561226924133":
                            self.state_data["status_message"] = "Demo client_id detected – using plain‑text Rich Presence."
                    except Exception as e:
                        rpc = None
                        self.state_data["rpc_connected"] = False
                        self.state_data["status_message"] = f"Discord not found: {str(e)[:60]}"
                        with open("debug.log", "a") as f:
                            f.write(f"Connect Error: {str(e)}\n")

                if rpc is not None:
                    metadata = self.state_data.get("metadata")
                    episode_str = self.state_data.get("episode_str", "")
                    
                    # Clean title for display
                    # Clean title for display
                    details = self.state_data["title"]
                        
                    if len(details) < 2:
                        details = "Unknown Track"
                    if len(details) > 120:
                        details = details[:117] + "..."
                        
                    state_parts = []
                    if episode_str:
                        state_parts.append(episode_str)
                    if not state_parts:
                        artist = self.state_data["artist"]
                        if artist:
                            state_parts.append(f"by {artist}")
                            
                    state = " | ".join(state_parts) if state_parts else ("Local Media" if self.state_data["length"] > 0 else "Streaming")
                    if len(state) < 2:
                        state = "Playing"
                    if len(state) > 120:
                        state = state[:117] + "..."
                        
                    now_ts = time.time()
                    start_time = None
                    end_time = None
                    
                    if playback_state == "playing":
                        start_time = int(now_ts - self.state_data["time"])
                        if self.state_data["length"] > 0:
                            end_time = int(start_time + self.state_data["length"])
                        small_img = config.get("small_image_key", "play")
                        small_txt = config.get("small_image_text", "Playing")
                    else:
                        state = f"Paused | {state}"
                        if len(state) > 120:
                            state = state[:117] + "..."
                        small_img = config.get("small_image_paused_key", "pause")
                        small_txt = config.get("small_image_paused_text", "Paused")
                        
                    large_img = config.get("large_image_key", "vlc")
                    if metadata and metadata.get("image_url"):
                        large_img = metadata.get("image_url")
                        
                    large_txt = config.get("large_image_text", "VLC Media Player")
                    
                    # Determine activity type
                    is_music = is_music_file(self.state_data["title"], self.state_data["artist"], self.state_data["album"])
                    act_type = ActivityType.LISTENING if is_music else ActivityType.WATCHING
                    
                    payload = {
                        "details": details,
                        "state": state,
                        "activity_type": act_type
                    }
                    if start_time is not None:
                        payload["start"] = start_time
                    if end_time is not None:
                        payload["end"] = end_time
                        
                    payload["large_image"] = large_img
                    payload["large_text"] = large_txt
                    
                    # Only add small images if we aren't using the demo ID, since it lacks those uploaded assets
                    if client_id != "1347834940380676156" and client_id != "963617561226924133":
                        payload["small_image"] = small_img
                        payload["small_text"] = small_txt
                        
                    if payload != last_presence_payload or (now_ts - last_update_time) > 15:
                        try:
                            rpc.update(**payload)
                            last_presence_payload = payload
                            last_update_time = now_ts
                            rpc_retry_count = 0
                            self.state_data["status_message"] = f"Discord active: {details[:30]}..."
                        except Exception as e:
                            with open("debug.log", "a") as f:
                                f.write(f"Update Error: {str(e)}\n")
                            rpc_retry_count += 1
                            err_msg = str(e)[:80]
                            self.state_data["status_message"] = f"RPC error (attempt {rpc_retry_count}): {err_msg}"
                            if rpc_retry_count >= 3:
                                try:
                                    rpc.close()
                                except Exception:
                                    pass
                                rpc = None
                                self.state_data["rpc_connected"] = False
                                last_presence_payload = {}
                                rpc_retry_count = 0
                                self.state_data["status_message"] = f"Discord disconnected: {err_msg}"
            else:
                if rpc is not None:
                    if last_presence_payload:
                        try:
                            rpc.clear()
                            last_presence_payload = {}
                            self.state_data["status_message"] = "Presence cleared (VLC stopped/idle)."
                        except Exception:
                            try:
                                rpc.close()
                            except Exception:
                                pass
                            rpc = None
                            self.state_data["rpc_connected"] = False
                            last_presence_payload = {}
            
            poll_time = config.get("update_interval", 2)
            time.sleep(poll_time)

    def fetch_itunes_metadata(self, title, artist):
        term = f"{artist} {title}" if artist else title
        try:
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(term)}&media=music&limit=1"
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                if results:
                    track = results[0]
                    img_url = track.get("artworkUrl100", "")
                    if img_url:
                        # Request high resolution image
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
            # If we have episode info, fetch with embedded episodes for episode-specific images
            embed = "&embed=episodes" if (season_num is not None or episode_num is not None) else ""
            url = f"https://api.tvmaze.com/singlesearch/shows?q={urllib.parse.quote(title)}{embed}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                
                # Default to show-level image
                img_url = None
                if data.get("image"):
                    img_url = data["image"].get("original") or data["image"].get("medium")
                
                rating = None
                if data.get("rating"):
                    rating = data["rating"].get("average")
                
                # Try to find episode-specific image
                if embed and data.get("_embedded", {}).get("episodes"):
                    episodes = data["_embedded"]["episodes"]
                    matched_ep = None
                    
                    if season_num is not None and episode_num is not None:
                        # TVMaze may use year-based seasons for some shows
                        # First try exact season/number match
                        matched_ep = next((ep for ep in episodes if ep.get("season") == season_num and ep.get("number") == episode_num), None)
                        
                        # If not found, try using absolute episode number (e.g. S01E15 = 15th episode overall)
                        if not matched_ep:
                            abs_index = (season_num - 1) * 100 + episode_num - 1  # rough guess
                            # Better: just use the episode_num as absolute index
                            if episode_num <= len(episodes):
                                matched_ep = episodes[episode_num - 1]
                    elif episode_num is not None:
                        # Absolute episode number
                        if episode_num <= len(episodes):
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
        # First try searching title with "film" suffix
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

    def download_cover_image(self, url):
        if not os.path.exists(COVERS_DIR):
            os.makedirs(COVERS_DIR)
            
        ext = ".jpg"
        parsed = urllib.parse.urlparse(url)
        path_ext = os.path.splitext(parsed.path)[1].lower()
        if path_ext in [".png", ".jpg", ".jpeg", ".webp"]:
            ext = path_ext
            
        filename = os.path.join(COVERS_DIR, hashlib.md5(url.encode()).hexdigest() + ext)
        if os.path.exists(filename):
            return filename
            
        try:
            r = requests.get(url, timeout=5, headers={"User-Agent": "VLC-Discord-RPC-Client/1.0"})
            if r.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(r.content)
                return filename
        except Exception:
            pass
        return None

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
            return config
    except Exception:
        return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass



backend = RPCBackend()

@eel.expose
def get_config():
    return backend.config

@eel.expose
def save_config(new_config):
    try:
        backend.config.update(new_config)
        save_config_func(backend.config)  # using the global one
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@eel.expose
def force_update():
    eel.updateState(backend.state_data)()

def update_ui_loop():
    while not backend.state_data["exit_flag"]:
        eel.updateState(backend.state_data)()
        eel.sleep(1)

def setup_tray():
    def on_quit(icon, item):
        backend.state_data["exit_flag"] = True
        icon.stop()
        os._exit(0)
        
    def on_show(icon, item):
        # We cannot easily unminimize Eel window cross-platform from a background thread
        pass
        
    image_path = "web/icon.ico"
    if os.path.exists(image_path):
        image = Image.open(image_path)
    else:
        image = Image.new('RGB', (64, 64), color='black')
        
    menu = pystray.Menu(pystray.MenuItem('Quit', on_quit))
    icon = pystray.Icon("vlc_rpc", image, "VLC Discord RP", menu)
    icon.run()

if __name__ == '__main__':
    # Need to alias the global save_config to avoid shadowing in Eel
    global save_config_func
    save_config_func = save_config

    threading.Thread(target=setup_tray, daemon=True).start()
    
    eel.init('web')
    eel.spawn(update_ui_loop)
    
    try:
        eel.start('index.html', size=(680, 640), port=0)
    except (SystemExit, KeyboardInterrupt):
        pass
        
    backend.state_data["exit_flag"] = True
    os._exit(0)
