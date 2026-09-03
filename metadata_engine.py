import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable
from concurrent.futures import Future

logger = logging.getLogger("VLC_RPC.MetadataEngine")

@dataclass
class MediaIdentity:
    title: str = ""
    base_title: str = ""
    season: Optional[int] = None
    episode: Optional[int] = None
    year: Optional[int] = None
    media_type: str = ""
    file_path: str = ""
    filename: str = ""

@dataclass
class MetadataResult:
    identity: MediaIdentity = field(default_factory=MediaIdentity)
    anilist_id: Optional[int] = None
    episode_title: str = ""
    duration: Optional[int] = None
    
    confidence: float = 0.0
    recognition_method: str = "unresolved"
    verification_status: str = "unresolved"
    
    cache_hit: bool = False
    provider: str = ""
    resolved_at: float = 0.0
    
    is_stale: bool = False
    is_fallback: bool = False
    
    # Optional extended properties
    image_url: Optional[str] = None
    genres: list = field(default_factory=list)
    rating: Optional[float] = None
    synopsis: Optional[str] = None
    dominant_color: Optional[str] = None

    def to_dict(self):
        return {
            "identity": {
                "title": self.identity.title,
                "season": self.identity.season,
                "episode": self.identity.episode,
                "year": self.identity.year,
                "media_type": self.identity.media_type,
                "file_path": self.identity.file_path,
                "filename": self.identity.filename
            },
            "anilist_id": self.anilist_id,
            "episode_title": self.episode_title,
            "duration": self.duration,
            "confidence": self.confidence,
            "recognition_method": self.recognition_method,
            "verification_status": self.verification_status,
            "provider": self.provider,
            "resolved_at": self.resolved_at,
            "image_url": self.image_url,
            "genres": self.genres,
            "rating": self.rating,
            "synopsis": self.synopsis,
            "dominant_color": self.dominant_color
        }

    @classmethod
    def from_dict(cls, data: dict):
        ident_data = data.get("identity", {})
        identity = MediaIdentity(
            title=ident_data.get("title", ""),
            season=ident_data.get("season"),
            episode=ident_data.get("episode"),
            year=ident_data.get("year"),
            media_type=ident_data.get("media_type", ""),
            file_path=ident_data.get("file_path", ""),
            filename=ident_data.get("filename", "")
        )
        return cls(
            identity=identity,
            anilist_id=data.get("anilist_id"),
            episode_title=data.get("episode_title", ""),
            duration=data.get("duration"),
            confidence=data.get("confidence", 0.0),
            recognition_method=data.get("recognition_method", "unresolved"),
            verification_status=data.get("verification_status", "unresolved"),
            provider=data.get("provider", ""),
            resolved_at=data.get("resolved_at", 0.0),
            image_url=data.get("image_url"),
            genres=data.get("genres", []),
            rating=data.get("rating"),
            synopsis=data.get("synopsis"),
            dominant_color=data.get("dominant_color")
        )

class MetadataEngine:
    def __init__(self, cache_file: str = "metadata_cache.json", diagnostics_manager=None, config=None):
        self.cache_file = cache_file
        self.diagnostics_manager = diagnostics_manager
        self.config = config or {}
        
        self.cache: Dict[str, MetadataResult] = {}
        self.negative_cache: Dict[str, float] = {}  # key -> timestamp
        
        self._cache_lock = threading.Lock()
        self._in_flight: Dict[str, Future] = {}
        self._in_flight_lock = threading.Lock()
        
        self.load_cache()

    def load_cache(self):
        with self._cache_lock:
            if not os.path.exists(self.cache_file):
                self.cache = {}
                return
            
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    raw_cache = json.load(f)
                    
                migrated = False
                self.cache = {}
                for k, v in raw_cache.items():
                    if "identity" in v and "recognition_method" in v:
                        # Already new format
                        self.cache[k] = MetadataResult.from_dict(v)
                    else:
                        # Legacy format migration
                        identity = MediaIdentity(
                            title=v.get("title", ""),
                            media_type=v.get("type", "movie")
                        )
                        res = MetadataResult(
                            identity=identity,
                            image_url=v.get("image_url"),
                            genres=v.get("genres", []),
                            rating=v.get("rating"),
                            provider="legacy_migration",
                            confidence=0.8,
                            recognition_method="cache_migration",
                            verification_status="probable",
                            resolved_at=time.time()
                        )
                        self.cache[k] = res
                        migrated = True
                
                if migrated:
                    logger.info("Migrated legacy metadata cache to structured MetadataResult format.")
                    self._save_cache_unlocked()
            except Exception as e:
                logger.error(f"Failed to load metadata cache: {e}")
                self.cache = {}

    def _save_cache_unlocked(self):
        # Bounded growth
        if len(self.cache) > 5000:
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1].resolved_at, reverse=True)
            self.cache = dict(sorted_items[:4000])
            
        try:
            import tempfile
            temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(self.cache_file)))
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump({k: v.to_dict() for k, v in self.cache.items()}, f)
            os.replace(temp_path, self.cache_file)
        except Exception as e:
            logger.error(f"Atomic cache save failed: {e}")

    def save_cache(self):
        with self._cache_lock:
            self._save_cache_unlocked()
            
    def _emit_diagnostic(self, event_type: str, data: Any = None):
        if self.diagnostics_manager and hasattr(self.diagnostics_manager, "set_state"):
            if event_type == "cache_hit":
                self.diagnostics_manager.set_state("metadata", "HEALTHY", "Cache Hit", is_success=True)
            elif event_type == "resolved":
                self.diagnostics_manager.set_state("metadata", "HEALTHY", f"Resolved via {data.get('provider', 'unknown')}", is_success=True)
            elif event_type in ["unresolved", "negative_cache_hit"]:
                self.diagnostics_manager.set_state("metadata", "HEALTHY", "Unresolved / Negative Cache", is_success=True)
            elif event_type == "request_deduplicated":
                self.diagnostics_manager.set_state("metadata", "HEALTHY", "Request Deduplicated", is_success=True)

    # ── Cache Key Normalization ─────────────────────────────────────────────
    @staticmethod
    def _normalize_cache_key(title: str, season: Optional[int] = None, episode: Optional[int] = None, media_type: str = "") -> str:
        """Build a normalized, path-independent cache key from media identity.
        A renamed/moved file with the same title+episode still resolves to the
        same cache entry."""
        norm = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
        parts = [media_type or "unknown", norm]
        if season is not None:
            parts.append(f"s{season}")
        if episode is not None:
            parts.append(f"e{episode}")
        return ":".join(parts)

    @staticmethod
    def _path_cache_key(file_path: str) -> str:
        """Secondary cache key based on file path (for fast first-pass lookups)."""
        return f"path:{file_path}"

    def _cache_lookup(self, identity: 'MediaIdentity', file_path: str = "") -> Optional['MetadataResult']:
        """Dual-key cache lookup: try normalized identity key first, then path key."""
        norm_key = self._normalize_cache_key(identity.title, identity.season, identity.episode, identity.media_type)
        result = self.cache.get(norm_key)
        if result:
            result.cache_hit = True
            return result
        if file_path:
            path_key = self._path_cache_key(file_path)
            result = self.cache.get(path_key)
            if result:
                result.cache_hit = True
                return result
        return None

    def _cache_store(self, identity: 'MediaIdentity', result: 'MetadataResult', file_path: str = ""):
        """Store result under both normalized and path keys."""
        norm_key = self._normalize_cache_key(identity.title, identity.season, identity.episode, identity.media_type)
        with self._cache_lock:
            self.cache[norm_key] = result
            if file_path:
                self.cache[self._path_cache_key(file_path)] = result
            self._save_cache_unlocked()

    # ── Negative Caching & Backoff ──────────────────────────────────────────
    NEGATIVE_CACHE_TTL = 3600  # 1 hour before retrying a failed resolution
    PROVIDER_BACKOFF_INITIAL = 30  # seconds
    PROVIDER_BACKOFF_MAX = 1800  # 30 minutes

    def _is_negative_cached(self, cache_key: str) -> bool:
        ts = self.negative_cache.get(cache_key)
        if ts is None:
            return False
        if time.time() - ts > self.NEGATIVE_CACHE_TTL:
            del self.negative_cache[cache_key]
            return False
        return True

    def _set_negative_cache(self, cache_key: str):
        self.negative_cache[cache_key] = time.time()

    # ── Resolution API ──────────────────────────────────────────────────────
    def resolve_sync(self, file_path: str = "", filename: str = "", raw_title: str = "",
                     media_type_hint: str = "") -> Optional['MetadataResult']:
        """Fast-path, cache-only resolution. Never blocks on network.
        Returns MetadataResult if cached, None otherwise."""
        identity = self.parse_filename(raw_title or filename)
        if media_type_hint:
            identity.media_type = media_type_hint
        if file_path:
            identity.file_path = file_path

        with self._cache_lock:
            result = self._cache_lookup(identity, file_path)
        return result

    def resolve_async(self, file_path: str = "", filename: str = "", raw_title: str = "",
                      media_type_hint: str = "", artist: str = "", is_music: bool = False,
                      generation: Optional[int] = None,
                      on_complete: Optional[Callable[['MetadataResult', int], None]] = None) -> Future:
        """Full asynchronous resolution with deduplication.

        Returns a Future[MetadataResult]. If an identical request is already
        in-flight, returns the existing Future (deduplication).

        ``generation`` is the media_generation counter from the caller.
        ``on_complete`` is an optional callback invoked with (result, generation)
        when resolution finishes. The caller MUST verify that generation still
        matches the current media before applying the result.
        """
        identity = self.parse_filename(raw_title or filename)
        if media_type_hint:
            identity.media_type = media_type_hint
        if file_path:
            identity.file_path = file_path

        dedup_key = self._normalize_cache_key(identity.title, identity.season, identity.episode, identity.media_type)

        # Check for negative cache
        if self._is_negative_cached(dedup_key):
            future = Future()
            result = MetadataResult(
                identity=identity,
                verification_status="negative_cached",
                recognition_method="negative_cache",
                confidence=0.0,
                resolved_at=time.time()
            )
            future.set_result(result)
            self._emit_diagnostic("negative_cache_hit", {"key": dedup_key})
            return future

        # Deduplication: return existing in-flight future if same request
        with self._in_flight_lock:
            if dedup_key in self._in_flight:
                existing_future = self._in_flight[dedup_key]
                if not existing_future.done():
                    self._emit_diagnostic("request_deduplicated", {"key": dedup_key})
                    return existing_future

            future = Future()
            self._in_flight[dedup_key] = future

        # Launch background resolution
        def _resolve_worker():
            try:
                result = self._resolve_pipeline(identity, file_path, artist, is_music, generation)
                future.set_result(result)
                if on_complete and generation is not None:
                    on_complete(result, generation)
            except Exception as e:
                logger.error(f"Resolution pipeline error: {e}")
                error_result = MetadataResult(
                    identity=identity,
                    verification_status="error",
                    recognition_method="error",
                    confidence=0.0,
                    resolved_at=time.time()
                )
                future.set_result(error_result)
                self._set_negative_cache(dedup_key)
            finally:
                with self._in_flight_lock:
                    self._in_flight.pop(dedup_key, None)

        threading.Thread(target=_resolve_worker, daemon=True).start()
        return future

    # ── Resolution Pipeline ─────────────────────────────────────────────────
    def _resolve_pipeline(self, identity: 'MediaIdentity', file_path: str = "",
                          artist: str = "", is_music: bool = False,
                          generation: Optional[int] = None) -> 'MetadataResult':
        """Full resolution pipeline: cache → providers → gemini fallback."""

        # 1. Cache lookup
        with self._cache_lock:
            cached = self._cache_lookup(identity, file_path)
        if cached and cached.confidence >= 0.6:
            self._emit_diagnostic("cache_hit", {"title": identity.title})
            return cached

        # 2. Clean the search title
        search_title = re.sub(r'\b(19|20)\d{2}\b', '', identity.title)
        search_title = re.sub(r'[\(\)]', '', search_title).strip()
        search_title = re.sub(r'\bSeason\s+\d+\b', '', search_title, flags=re.IGNORECASE).strip()
        search_title = re.sub(r'\s{2,}', ' ', search_title).strip()

        season_num = identity.season
        episode_num = identity.episode
        media_type = identity.media_type or "movie"

        year_match = re.search(r'\((\d{4})\)', identity.title)
        year = year_match.group(1) if year_match else None

        logger.info(f"[Pipeline] Resolving '{search_title}' type={media_type} S{season_num}E{episode_num}")

        # 3. Provider chain (same priority order as existing _fetch_metadata_bg)
        provider_result = None

        if is_music or media_type == "music":
            provider_result = self.fetch_itunes_metadata(search_title, artist)
            if provider_result:
                provider_result["_provider"] = "itunes"

        elif media_type == "movie":
            provider_result = self.fetch_omdb_metadata(search_title, year)
            if provider_result:
                provider_result["_provider"] = "omdb"
            if not provider_result or not provider_result.get("image_url"):
                provider_result = self.fetch_anilist_metadata(search_title)
                if provider_result:
                    provider_result["_provider"] = "anilist"
            if not provider_result or not provider_result.get("image_url"):
                provider_result = self.fetch_jikan_metadata(search_title)
                if provider_result:
                    provider_result["_provider"] = "jikan"

        elif media_type == "anime":
            if season_num and season_num > 1:
                ordinals = {2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}
                suffix = ordinals.get(season_num, f"{season_num}th")
                provider_result = self.fetch_anilist_metadata(f"{search_title} {suffix} Season")
                if provider_result:
                    provider_result["_provider"] = "anilist"
            if not provider_result or not provider_result.get("image_url"):
                provider_result = self.fetch_anilist_metadata(search_title)
                if provider_result:
                    provider_result["_provider"] = "anilist"
            if not provider_result or not provider_result.get("image_url"):
                if season_num and season_num > 1:
                    ordinals = {2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}
                    suffix = ordinals.get(season_num, f"{season_num}th")
                    provider_result = self.fetch_jikan_metadata(f"{search_title} {suffix} Season")
                    if provider_result:
                        provider_result["_provider"] = "jikan"
            if not provider_result or not provider_result.get("image_url"):
                provider_result = self.fetch_jikan_metadata(search_title)
                if provider_result:
                    provider_result["_provider"] = "jikan"
            # Supplement rating from OMDb if missing
            if provider_result and not provider_result.get("rating"):
                omdb = self.fetch_omdb_metadata(search_title, year)
                if omdb and omdb.get("rating"):
                    provider_result["rating"] = omdb["rating"]

        elif media_type == "tv_show":
            provider_result = self.fetch_tvmaze_metadata(search_title, season_num=season_num, episode_num=episode_num)
            if provider_result:
                provider_result["_provider"] = "tvmaze"
            # If TVMaze found anime/animation, prefer AniList
            if provider_result and any(g.lower() in ("anime", "animation") for g in provider_result.get("genres", [])):
                anilist_meta = self.fetch_anilist_metadata(search_title)
                if anilist_meta and anilist_meta.get("image_url"):
                    provider_result = anilist_meta
                    provider_result["_provider"] = "anilist"
            if not provider_result or not provider_result.get("image_url"):
                provider_result = self.fetch_omdb_metadata(search_title, year)
                if provider_result:
                    provider_result["_provider"] = "omdb"
            if not provider_result or not provider_result.get("image_url"):
                provider_result = self.fetch_anilist_metadata(search_title)
                if provider_result:
                    provider_result["_provider"] = "anilist"
            if not provider_result or not provider_result.get("image_url"):
                provider_result = self.fetch_jikan_metadata(search_title)
                if provider_result:
                    provider_result["_provider"] = "jikan"

        # Wikipedia fallback for all types
        if not provider_result or not provider_result.get("image_url"):
            provider_result = self.fetch_wikipedia_metadata(search_title)
            if provider_result:
                provider_result["_provider"] = "wikipedia"

        # 4. Build MetadataResult
        if provider_result and provider_result.get("image_url"):
            result = MetadataResult(
                identity=identity,
                anilist_id=provider_result.get("anilistId"),
                confidence=0.85,
                recognition_method="provider",
                verification_status="verified",
                provider=provider_result.get("_provider", "unknown"),
                resolved_at=time.time(),
                image_url=provider_result.get("image_url"),
                genres=provider_result.get("genres", []),
                rating=provider_result.get("rating"),
                synopsis=provider_result.get("plot") or provider_result.get("description"),
            )
            self._cache_store(identity, result, file_path)
            self._emit_diagnostic("resolved", {"title": identity.title, "provider": result.provider})
            return result
        else:
            # Negative cache: prevent re-fetching every poll cycle
            dedup_key = self._normalize_cache_key(identity.title, identity.season, identity.episode, identity.media_type)
            self._set_negative_cache(dedup_key)
            self._emit_diagnostic("unresolved", {"title": identity.title})
            return MetadataResult(
                identity=identity,
                confidence=0.0,
                recognition_method="unresolved",
                verification_status="unresolved",
                resolved_at=time.time()
            )

    @staticmethod
    def parse_filename(title: str) -> MediaIdentity:
        """Parse a raw filename into structured media identity data."""
        title = str(title or "")
        title = re.sub(r'^\d+[\.\-]\s+', '', title)
        title = re.sub(r'\.(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', title, flags=re.I).strip()
        title = re.sub(r'\s+(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', title, flags=re.I).strip()
        
        def _bracket_to_subtitle(m):
            c = m.group(1).strip()
            if ' ' not in c and "'" not in c and re.match(r'^[\w\-\.]+$', c):
                return m.group(0)
            return ': ' + c
        title = re.sub(r'\[([^\]]+)\]', _bracket_to_subtitle, title)

        title = re.sub(r'([a-z])([A-Z])', r'\1 \2', title)
        title = title.replace(';', ':')

        def _smart_cap(w):
            if not w: return w
            if w.isupper() and len(w) <= 5: return w
            def cap_part(p):
                if not p: return p
                if any(c.isupper() for c in p[1:]): return p
                return p.capitalize()
            return '-'.join(cap_part(p) for p in w.split('-'))

        def _apply_smart_cap(t):
            if not t: return t
            return ' '.join(_smart_cap(w) for w in str(t).split())

        result = {
            "title": title,
            "base_title": "",
            "season": None,
            "episode": None,
            "media_type": ""
        }

        loose_ep = re.search(r"(?<!\d)([A-Za-z][\w\s\.'\.\-:&!,]+?)[\s\._]+(?:Episode|Ep|E)?\s*(\d{1,4})(?:v\d+)?\s*$", title, re.I)
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
            import guessit
            guessed = guessit.guessit(raw_title_for_guessit)
            cleaned = guessed.get('title', raw_title_for_guessit)
            media_type = guessed.get('type', '')

            if media_type == 'movie':
                year = guessed.get('year')
                if year:
                    cleaned = f"{cleaned} ({year})"
            
            release_group = guessed.get('release_group')
            if release_group and isinstance(release_group, str):
                rg = release_group.strip()
                if ("'" in rg or " " in rg) and len(rg) > 3 and cleaned and rg.lower() not in cleaned.lower():
                    cleaned = cleaned + ": " + rg
                    
            cleaned = _apply_smart_cap(cleaned)
            
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
            
        return MediaIdentity(
            title=result.get("title", title),
            base_title=result.get("base_title", ""),
            season=result.get("season"),
            episode=result.get("episode"),
            media_type=result.get("media_type", ""),
            filename=title
        )

    def query_gemini(self, filename: str, api_key: str) -> Optional[dict]:
        """Use Gemini REST API to get the exact official anime/media title and episode."""
        if not api_key: return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
        
        prompt = f"""
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
{{
  "title": "Overlord II",
  "base_title": "Overlord",
  "season": 2,
  "episode": 10,
  "media_type": "anime"
}}

Return ONLY valid JSON in this exact format:

{{
  "title": "...",
  "base_title": "...",
  "season": <number or null>,
  "episode": <number or null>,
  "media_type": "anime|movie|tv_show|song|music|unknown"
}}

Filename:
{filename}
"""
        
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
            logger.warning(f"Gemini API error: {e}")
            pass
        return None

    def fetch_anilist_metadata(self, title: str) -> Optional[dict]:
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
            import requests
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

    def fetch_omdb_metadata(self, title: str, year: Optional[int] = None) -> Optional[dict]:
        try:
            import requests
            params = {
                't': title,
                'apikey': 'thewdb',
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
                    if poster == 'N/A': poster = None
                    rating = data.get('imdbRating')
                    if rating == 'N/A': rating = None
                    genres = [g.strip() for g in data.get('Genre', '').split(',') if g.strip() and g.strip() != 'N/A']
                    plot = data.get('Plot', '')
                    if plot == 'N/A': plot = ''
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

    def fetch_tvmaze_metadata(self, title: str, season_num: Optional[int] = None, episode_num: Optional[int] = None) -> Optional[dict]:
        try:
            import urllib.parse
            import requests
            embed = "&embed=episodes" if (season_num is not None or episode_num is not None) else ""
            url = f"https://api.tvmaze.com/singlesearch/shows?q={urllib.parse.quote(title)}{embed}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                img_url = None
                if data.get("image"):
                    img_url = data["image"].get("original") or data["image"].get("medium")
                rating = data.get("rating", {}).get("average") if data.get("rating") else None
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
                        if ep_img: img_url = ep_img
                
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
                    "total_episodes": len(data.get("_embedded", {}).get("episodes", [])) if embed else 0
                }
        except Exception:
            pass
        return None

    def fetch_jikan_metadata(self, title: str) -> Optional[dict]:
        try:
            import urllib.parse
            import requests
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

            short = ' '.join(title.split()[:3])
            if short != title:
                url2 = f"https://api.jikan.moe/v4/anime?q={urllib.parse.quote(short)}&limit=5"
                r2 = requests.get(url2, timeout=5)
                if r2.status_code == 200:
                    results2 = r2.json().get("data", [])
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

    def fetch_wikipedia_metadata(self, title: str) -> Optional[dict]:
        meta = self._search_wikipedia(f"{title} film")
        if not meta:
            meta = self._search_wikipedia(title)
        return meta

    def _search_wikipedia(self, query: str) -> Optional[dict]:
        try:
            import urllib.parse
            import requests
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json"
            r = requests.get(search_url, timeout=3)
            if r.status_code == 200:
                results = r.json().get("query", {}).get("search", [])
                if results:
                    best_title = results[0]["title"]
                    img_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(best_title)}&prop=pageimages&format=json&pithumbsize=500"
                    img_r = requests.get(img_url, timeout=3)
                    if img_r.status_code == 200:
                        pages = img_r.json().get("query", {}).get("pages", {})
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

    def fetch_itunes_metadata(self, title: str, artist: str) -> Optional[dict]:
        try:
            import urllib.parse
            import requests
            query = f"{title} {artist}"
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&media=music&limit=1"
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                results = r.json().get("results", [])
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
