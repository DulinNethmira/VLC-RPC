with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Trust AniList and other known CDNs directly in normalize_cover_url
old_scheme_check = '''        if parsed.scheme not in ("http", "https") or not parsed.netloc:\r\n\r\n\r\n            return None\r\n\r\n\r\n\r\n\r\n\r\n        headers = {'''
new_scheme_check = '''        if parsed.scheme not in ("http", "https") or not parsed.netloc:\r\n\r\n\r\n            return None\r\n\r\n\r\n        # Trust well-known image CDNs directly (AniList serves WebP without file extensions)\r\n        TRUSTED_CDNS = (\r\n            "s4.anilist.co", "s1.anilist.co", "s3.anilist.co", "anilist.co",\r\n            "cdn.myanimelist.net", "media.kitsu.io",\r\n            "image.tmdb.org", "artworks.thetvdb.com",\r\n            "m.media-amazon.com",\r\n        )\r\n        if any(parsed.netloc.endswith(cdn) for cdn in TRUSTED_CDNS):\r\n            return url\r\n\r\n        headers = {'''

if old_scheme_check in content:
    content = content.replace(old_scheme_check, new_scheme_check)
    print("Fix 1 applied: CDN trust bypass")
else:
    print("Fix 1 NOT applied - pattern not found")
    # Try without carriage returns
    old2 = '        if parsed.scheme not in ("http", "https") or not parsed.netloc:\n\n\n            return None\n\n\n\n\n\n        headers = {'
    if old2 in content:
        content = content.replace(old2, old2.replace('\n\n\n\n\n\n        headers = {', '\n\n\n        # Trust well-known image CDNs directly (AniList serves WebP without file extensions)\n        TRUSTED_CDNS = (\n            "s4.anilist.co", "s1.anilist.co", "s3.anilist.co", "anilist.co",\n            "cdn.myanimelist.net", "media.kitsu.io",\n            "image.tmdb.org", "artworks.thetvdb.com",\n            "m.media-amazon.com",\n        )\n        if any(parsed.netloc.endswith(cdn) for cdn in TRUSTED_CDNS):\n            return url\n\n        headers = {'))
        print("Fix 1 (alt) applied")
    else:
        print("Fix 1 FAILED - manual fix needed")

# Fix 2: Also bypass the base64 download for trusted CDN URLs - it's causing slowdowns
old_base64 = '''        if image_url and not image_url.startswith("data:image/"):

            try:

'''
new_base64 = '''        # Skip base64 encoding for trusted CDNs - they render fine directly in pywebview
        TRUSTED_CDNS_B64 = ("s4.anilist.co", "s1.anilist.co", "s3.anilist.co", "anilist.co",
            "cdn.myanimelist.net", "media.kitsu.io", "image.tmdb.org", "m.media-amazon.com")
        import urllib.parse as _up
        _parsed_img = _up.urlparse(image_url) if image_url else None
        _is_trusted = _parsed_img and any(_parsed_img.netloc.endswith(c) for c in TRUSTED_CDNS_B64)
        if _is_trusted:
            metadata["image_data_uri"] = image_url  # Use URL directly - pywebview can load it
        elif image_url and not image_url.startswith("data:image/"):

            try:

'''

if old_base64 in content:
    content = content.replace(old_base64, new_base64)
    print("Fix 2 applied: Skip base64 for trusted CDNs")
else:
    print("Fix 2 NOT applied - searching differently...")
    # Count occurrences of key phrase
    idx = content.find('if image_url and not image_url.startswith("data:image/")')
    print(f"  Found at index: {idx}")

# Fix 3: Ensure Discord is cleared when VLC disconnects (add explicit rpc.clear)
old_vlc_disconnect = '''                    self.state_data["vlc_connected"] = False
                    if getattr(self, "diagnostics", None):
                        self.diagnostics.set_state("vlc", "OFFLINE", "VLC disconnected")


                    self.state_data["playback_state"] = "stopped"'''

new_vlc_disconnect = '''                    self.state_data["vlc_connected"] = False
                    if getattr(self, "diagnostics", None):
                        self.diagnostics.set_state("vlc", "OFFLINE", "VLC disconnected")
                    # Immediately clear Discord presence when VLC closes
                    try:
                        if getattr(self, "discord_manager", None):
                            self.discord_manager.clear_activity(self.media_generation)
                    except Exception:
                        pass

                    self.state_data["playback_state"] = "stopped"'''

if old_vlc_disconnect in content:
    content = content.replace(old_vlc_disconnect, new_vlc_disconnect)
    print("Fix 3 applied: Clear Discord on VLC disconnect")
else:
    print("Fix 3 NOT applied - pattern not found")

with open('vlc_discord_rpc_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done!")
