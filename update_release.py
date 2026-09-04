import re

with open('build_release.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(
    r'release_title = \".*?\"',
    'release_title = "✨ v6.1.5 - Cover Art Fix, Force Sync & Disconnect Fix"',
    c
)

c = re.sub(
    r'release_notes = \"\"\".*?\"\"\"',
    'release_notes = """### 🚀 What\'s New in v6.1.5!\n\n#### 🖼️ Cover Art Now Works Properly\n- **AniList CDN Fix**: Cover images from AniList now load correctly for all anime.\n- **Trusted CDN Bypass**: AniList, MAL, Kitsu, TMDB cover URLs are now trusted directly without slow HTTP validation that was causing covers to fail.\n- **No More Base64 Re-encoding**: CDN images are served directly to the UI without being re-downloaded, making metadata load much faster.\n\n#### 🎮 Force Sync Button Restored\n- The **Force Sync** button is back in the Dashboard header, clearly labeled.\n- One click syncs your AniList profile widget AND triggers a metadata refresh.\n- Animated states: syncing ➔ synced ✔\n\n#### ⏹️ Discord RPC Clears Instantly on VLC Close\n- Fixed bug where Discord activity kept showing even after VLC was closed.\n- Discord presence now clears immediately when VLC disconnects.\n\n### 🔧 Fixes & Tweaks\n- System Health indicator correctly reports 100% when no errors exist.\n- Improved error handling throughout.\n\nEnjoy the update! 🎉"""',
    c,
    flags=re.DOTALL
)

with open('build_release.py', 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated build_release.py')
