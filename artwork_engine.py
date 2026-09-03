import os
import time
import json
import base64
import hashlib
import mimetypes
import threading
import urllib.parse
import urllib.request
import logging
import requests
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class ArtworkResult:
    source: str          # "EMBEDDED", "LOCAL", "CACHE", "REMOTE", "FALLBACK"
    provider: str        # "VLC", "AniList", "OMDb", "Imgur", "None", etc.
    local_path: str      # Path to the locally cached image
    frontend_url: str    # URL or base64 suitable for frontend rendering
    discord_url: str     # Public HTTPS URL suitable for Discord RPC
    cache_key: str
    validation_status: str # "VALID", "INVALID", "PENDING"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "provider": self.provider,
            "frontend_url": self.frontend_url,
            "discord_url": self.discord_url,
            "validation_status": self.validation_status
        }

class ArtworkEngine:
    """
    Centralized artwork resolution and caching engine.
    Ensures safe, non-blocking artwork retrieval for VLC RPC.
    """
    
    def __init__(self, cache_dir: str, config: dict, logger=None):
        self.cache_dir = cache_dir
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        self.cache_index_path = os.path.join(self.cache_dir, "artwork_index.json")
        self.cache_index: Dict[str, dict] = {}
        
        self.lock = threading.RLock()
        self.in_flight_tasks: Dict[str, threading.Thread] = {}
        self.in_flight_results: Dict[str, ArtworkResult] = {}
        
        # Diagnostics
        self.metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "download_failures": 0,
            "validation_failures": 0,
            "upload_failures": 0,
            "last_success": None,
            "last_failure": None,
            "active_provider": "None"
        }
        
        self._init_cache()

    def _init_cache(self):
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            
        if os.path.exists(self.cache_index_path):
            try:
                with open(self.cache_index_path, "r", encoding="utf-8") as f:
                    self.cache_index = json.load(f)
            except Exception as e:
                self.logger.error(f"[ArtworkEngine] Failed to load cache index: {e}")
                self.cache_index = {}
                
        self._enforce_cache_limits()

    def _save_cache(self):
        try:
            with open(self.cache_index_path, "w", encoding="utf-8") as f:
                json.dump(self.cache_index, f)
        except Exception as e:
            self.logger.error(f"[ArtworkEngine] Failed to save cache index: {e}")

    def _enforce_cache_limits(self, max_items=200):
        with self.lock:
            if len(self.cache_index) > max_items:
                sorted_items = sorted(
                    self.cache_index.items(),
                    key=lambda x: x[1].get("last_used", 0)
                )
                items_to_remove = sorted_items[:len(self.cache_index) - max_items]
                for key, data in items_to_remove:
                    local_path = data.get("local_path")
                    if local_path and os.path.exists(local_path):
                        try:
                            os.remove(local_path)
                        except Exception:
                            pass
                    del self.cache_index[key]
                self._save_cache()

    def _generate_key(self, identity: str) -> str:
        # Identity is already a stable hash (e.g. md5 of filename or anilist id)
        return identity

    def get_diagnostics(self) -> dict:
        with self.lock:
            return dict(self.metrics)

    def resolve_artwork_fast(self, identity: str) -> Optional[ArtworkResult]:
        """Fast synchronous lookup for existing valid cached artwork."""
        cache_key = self._generate_key(identity)
        with self.lock:
            if cache_key in self.cache_index:
                entry = self.cache_index[cache_key]
                local_path = entry.get("local_path")
                if local_path and os.path.exists(local_path):
                    self.metrics["cache_hits"] += 1
                    entry["last_used"] = time.time()
                    return ArtworkResult(
                        source=entry.get("source", "CACHE"),
                        provider=entry.get("provider", "Unknown"),
                        local_path=local_path,
                        frontend_url=self._get_frontend_url(local_path),
                        discord_url=entry.get("discord_url", ""),
                        cache_key=cache_key,
                        validation_status="VALID"
                    )
            self.metrics["cache_misses"] += 1
            return None

    def resolve_artwork_bg(self, identity: str, vlc_data: dict, metadata_url: str = None) -> None:
        """Asynchronously resolve artwork, avoiding duplication if already in flight."""
        cache_key = self._generate_key(identity)
        
        with self.lock:
            if cache_key in self.in_flight_tasks:
                return # Already processing
                
            task_thread = threading.Thread(
                target=self._resolve_worker,
                args=(cache_key, identity, vlc_data, metadata_url),
                daemon=True
            )
            self.in_flight_tasks[cache_key] = task_thread
            task_thread.start()

    def get_in_flight_result(self, cache_key: str) -> Optional[ArtworkResult]:
        with self.lock:
            return self.in_flight_results.get(cache_key)

    def _resolve_worker(self, cache_key: str, identity: str, vlc_data: dict, metadata_url: str):
        try:
            result = self._do_resolve(cache_key, identity, vlc_data, metadata_url)
            with self.lock:
                if result:
                    self.in_flight_results[cache_key] = result
                    self.metrics["last_success"] = time.time()
                    self.metrics["active_provider"] = result.provider
                    
                    self.cache_index[cache_key] = {
                        "source": result.source,
                        "provider": result.provider,
                        "local_path": result.local_path,
                        "discord_url": result.discord_url,
                        "last_used": time.time(),
                        "created": time.time()
                    }
                    self._save_cache()
                    self._enforce_cache_limits()
        except Exception as e:
            self.logger.error(f"[ArtworkEngine] Unhandled exception resolving artwork: {e}")
        finally:
            with self.lock:
                if cache_key in self.in_flight_tasks:
                    del self.in_flight_tasks[cache_key]

    def _do_resolve(self, cache_key: str, identity: str, vlc_data: dict, metadata_url: str) -> Optional[ArtworkResult]:
        # 1. Embedded Artwork
        embedded_result = self._extract_vlc_art(vlc_data, cache_key)
        if embedded_result:
            return embedded_result
            
        # 2. Remote Metadata Artwork
        if metadata_url:
            remote_result = self._download_remote_art(metadata_url, cache_key)
            if remote_result:
                return remote_result
                
        # (Local folder art could be added here as #1.5)
        
        return None

    def _extract_vlc_art(self, vlc_data: dict, cache_key: str) -> Optional[ArtworkResult]:
        if not vlc_data:
            return None
            
        vlc_art_url = vlc_data.get("artwork_url", "")
        if not vlc_art_url:
            return None
            
        local_path = os.path.join(self.cache_dir, f"{cache_key}_embedded.jpg")
        
        if vlc_art_url.startswith("file:///"):
            art_path = urllib.parse.unquote(vlc_art_url[8:]).replace("/", os.sep)
            if os.path.isfile(art_path):
                # Copy to cache for consistency and validation
                if self._validate_and_copy(art_path, local_path):
                    discord_url = self._get_or_upload_imgur(local_path, cache_key)
                    return ArtworkResult("EMBEDDED", "VLC", local_path, self._get_frontend_url(local_path), discord_url, cache_key, "VALID")
        else:
            # Fallback to VLC API /art
            vlc_host = self.config.get("vlc_host", "localhost")
            vlc_port = self.config.get("vlc_port", 8080)
            vlc_pw = self.config.get("vlc_password", "")
            try:
                ar = requests.get(f"http://{vlc_host}:{vlc_port}/art", auth=requests.auth.HTTPBasicAuth("", vlc_pw), timeout=2)
                if ar.status_code == 200 and ar.headers.get("Content-Type", "").startswith("image"):
                    with open(local_path, "wb") as f:
                        f.write(ar.content)
                    if self._validate_image(local_path):
                        discord_url = self._get_or_upload_imgur(local_path, cache_key)
                        return ArtworkResult("EMBEDDED", "VLC", local_path, self._get_frontend_url(local_path), discord_url, cache_key, "VALID")
            except Exception:
                pass
                
        return None

    def _download_remote_art(self, url: str, cache_key: str) -> Optional[ArtworkResult]:
        local_path = os.path.join(self.cache_dir, f"{cache_key}_remote.jpg")
        
        try:
            r = requests.get(url, stream=True, timeout=5)
            if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image"):
                # Size limit 10MB
                content_length = int(r.headers.get("Content-Length", 0))
                if content_length > 10 * 1024 * 1024:
                    self.logger.warning(f"[ArtworkEngine] Image too large: {content_length} bytes")
                    self._record_validation_failure()
                    return None
                    
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                if self._validate_image(local_path):
                    provider = "Remote"
                    if "anilist" in url: provider = "AniList"
                    elif "jikan" in url: provider = "Jikan"
                    elif "omdb" in url: provider = "OMDb"
                    
                    return ArtworkResult("REMOTE", provider, local_path, self._get_frontend_url(local_path), url, cache_key, "VALID")
            else:
                self._record_download_failure(f"HTTP {r.status_code}")
        except requests.RequestException as e:
            self._record_download_failure(str(e))
            
        return None

    def _get_or_upload_imgur(self, local_path: str, cache_key: str) -> str:
        """Upload to Imgur only if not already uploaded. (Discord RPC requires HTTPS)"""
        with self.lock:
            existing = self.cache_index.get(cache_key)
            if existing and existing.get("discord_url") and "imgur.com" in existing.get("discord_url"):
                return existing["discord_url"]
                
        try:
            with open(local_path, "rb") as f:
                image_data = f.read()
                
            upload = requests.post(
                "https://api.imgur.com/3/image",
                headers={"Authorization": "Client-ID 546c25a59c58ad7"},
                data={"image": base64.b64encode(image_data).decode('utf-8')},
                timeout=10
            )
            
            if upload.status_code == 200:
                url = upload.json().get("data", {}).get("link", "")
                if url:
                    return url.replace("http://", "https://")
            else:
                self._record_upload_failure(f"HTTP {upload.status_code}")
        except Exception as e:
            self._record_upload_failure(str(e))
            
        return ""

    def _validate_image(self, local_path: str) -> bool:
        if not os.path.exists(local_path):
            return False
        size = os.path.getsize(local_path)
        if size == 0 or size > 10 * 1024 * 1024:
            self._record_validation_failure()
            return False
            
        # Basic header magic byte check
        try:
            with open(local_path, "rb") as f:
                header = f.read(12)
                # JPEG, PNG, WEBP, GIF
                valid = (
                    header.startswith(b'\xff\xd8') or
                    header.startswith(b'\x89PNG\r\n\x1a\n') or
                    header[8:12] == b'WEBP' or
                    header.startswith(b'GIF8')
                )
                if not valid:
                    self._record_validation_failure()
                return valid
        except Exception:
            self._record_validation_failure()
            return False

    def _validate_and_copy(self, src: str, dst: str) -> bool:
        import shutil
        try:
            if not self._validate_image(src):
                return False
            shutil.copy2(src, dst)
            return True
        except Exception:
            return False

    def _get_frontend_url(self, local_path: str) -> str:
        """
        Returns a local file URI to avoid massive base64 payloads blocking the UI.
        Works safely with pywebview's local file serving architecture.
        """
        if not local_path or not os.path.exists(local_path):
            return ""
        
        # Format Windows path to valid file URI
        safe_path = local_path.replace(os.sep, "/")
        if not safe_path.startswith("/"):
            safe_path = "/" + safe_path
            
        return f"file://{safe_path}"

    def _record_download_failure(self, reason: str):
        with self.lock:
            self.metrics["download_failures"] += 1
            self.metrics["last_failure"] = f"Download Failed: {reason}"

    def _record_validation_failure(self):
        with self.lock:
            self.metrics["validation_failures"] += 1
            self.metrics["last_failure"] = "Validation Failed: Invalid format/size"

    def _record_upload_failure(self, reason: str):
        with self.lock:
            self.metrics["upload_failures"] += 1
            self.metrics["last_failure"] = f"Upload Failed: {reason}"
