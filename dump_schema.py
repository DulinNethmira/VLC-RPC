import re
content = open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8').read()
match = re.search(r'CREATE TABLE IF NOT EXISTS history(.*?)\)', content, re.DOTALL)
if match:
    print(match.group(0))
