import re

# setup.iss
with open('setup.iss', 'r', encoding='utf-8') as f:
    c = f.read()
c = re.sub(r'AppVersion=[\d\.]+', 'AppVersion=6.2.0', c)
c = re.sub(r'OutputBaseFilename=VLC RPC Setup v[\d\.]+', 'OutputBaseFilename=VLC RPC Setup v6.2.0', c)
with open('setup.iss', 'w', encoding='utf-8') as f:
    f.write(c)

# version_info.txt
with open('version_info.txt', 'r', encoding='utf-8') as f:
    c = f.read()
c = re.sub(r'filevers=\([\d,\s]+\)', 'filevers=(6, 2, 0, 0)', c)
c = re.sub(r'prodvers=\([\d,\s]+\)', 'prodvers=(6, 2, 0, 0)', c)
c = re.sub(r"StringStruct\(u'FileVersion', u'[\d\.]+'\)", "StringStruct(u'FileVersion', u'6.2.0')", c)
c = re.sub(r"StringStruct\(u'ProductVersion', u'[\d\.]+'\)", "StringStruct(u'ProductVersion', u'6.2.0')", c)
with open('version_info.txt', 'w', encoding='utf-8') as f:
    f.write(c)

# vlc_discord_rpc_gui.py
with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = re.sub(r'CURRENT_VERSION = \"[\d\.]+\"', 'CURRENT_VERSION = \"6.2.0\"', c)
with open('vlc_discord_rpc_gui.py', 'w', encoding='utf-8') as f:
    f.write(c)


