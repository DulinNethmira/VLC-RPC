files = ['vlc_discord_rpc_gui.py', 'setup.iss', 'version_info.txt', 'build_release.py']
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        c = file.read()
    c = c.replace('6.1.4', '6.1.5')
    with open(f, 'w', encoding='utf-8') as file:
        file.write(c)
    print(f'Bumped {f}')

# Update release notes in build_release.py  
with open('build_release.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace(
    'tag_name = "v6.1.5"',
    'tag_name = "v6.1.5"'
)
# Update title and notes
import re
c = re.sub(
    r'release_title = ".*?"',
    r'release_title = "\u2728 v6.1.5 - Cover Art Fix, Force Sync & Disconnect Fix"',
    c
)
c = re.sub(
    r'release_notes = """.*?"""',
    '''release_notes = """### \U0001f680 What\'s New in v6.1.5!

#### \U0001f5bc\ufe0f Cover Art Now Works Properly
- **AniList CDN Fix**: Cover images from AniList now load correctly for all anime.
- **Trusted CDN Bypass**: AniList, MAL, Kitsu, TMDB cover URLs are now trusted directly without slow HTTP validation that was causing covers to fail.
- **No More Base64 Re-encoding**: CDN images are served directly to the UI without being re-downloaded, making metadata load much faster.

#### \U0001f3ae Force Sync Button Restored
- The **Force Sync** button is back in the Dashboard header, clearly labeled.
- One click syncs your AniList profile widget AND triggers a metadata refresh.
- Animated states: syncing \u279c synced \u2714

#### \u23f9\ufe0f Discord RPC Clears Instantly on VLC Close
- Fixed bug where Discord activity kept showing even after VLC was closed.
- Discord presence now clears immediately when VLC disconnects.

### \U0001f527 Fixes & Tweaks
- System Health indicator correctly reports 100% when no errors exist.
- Improved error handling throughout.

Enjoy the update! \U0001f389"""''',
    c,
    flags=re.DOTALL
)
with open('build_release.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('Release notes updated')
