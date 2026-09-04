import re

files = ['vlc_discord_rpc_gui.py', 'setup.iss', 'version_info.txt']
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        c = file.read()
    c = c.replace('6.1.5', '6.1.6')
    with open(f, 'w', encoding='utf-8') as file:
        file.write(c)
    print(f'Bumped {f}')

with open('build_release.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('6.1.5', '6.1.6')

c = re.sub(
    r'release_title = \".*?\"',
    'release_title = "✨ v6.1.6 - History Crash & Cover Cache Fixes"',
    c
)

c = re.sub(
    r'release_notes = \"\"\".*?\"\"\"',
    'release_notes = """### 🚀 What\'s New in v6.1.6!\n\n#### 🖼️ UI & Cover Arts\n- **History Covers**: Fixed a bug where cover arts would not load correctly for history items in the "Continue Watching" and "Dashboard" sections. Cover images now properly match against cached metadata identities.\n\n#### 🔧 Bug Fixes\n- **History Crash**: Resolved a critical backend error (`add_to_history() takes 5 positional arguments but 6 were given`) that occurred when stopping playback, ensuring watch times save correctly.\n\nEnjoy the update! 🎉"""',
    c,
    flags=re.DOTALL
)

with open('build_release.py', 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated build_release.py')
