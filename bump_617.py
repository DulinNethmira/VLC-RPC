import os

def bump(filename, old, new):
    if not os.path.exists(filename): return
    with open(filename, 'r', encoding='utf-8') as f:
        c = f.read()
    c = c.replace(old, new)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(c)
    print(f"Bumped {filename}")

bump('vlc_discord_rpc_gui.py', "CURRENT_VERSION = '6.1.6'", "CURRENT_VERSION = '6.1.7'")
bump('vlc_discord_rpc_gui.py', 'CURRENT_VERSION = "6.1.6"', 'CURRENT_VERSION = "6.1.7"')
bump('setup.iss', '6.1.6', '6.1.7')
bump('version_info.txt', '6, 1, 6, 0', '6, 1, 7, 0')
bump('build_release.py', '6.1.6', '6.1.7')
