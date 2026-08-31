"""fix_release_notes.py - Fix the escaped unicode in build_release.py"""
with open('build_release.py', 'r', encoding='utf-8') as f:
    src = f.read()

old_title = '    release_title = "\\u2728 v5.6.4 - Rock-Solid Discord Connection \\u0026 Dead Pipe Recovery"'
new_title = '    release_title = "\u2728 v5.6.4 - Rock-Solid Discord Connection & Dead Pipe Recovery"'

old_notes_start = '    release_notes = """### \\U0001f680'
new_notes_start = '    release_notes = """### \U0001f680'

src = src.replace(old_title, new_title)
src = src.replace('\\U0001f680', '\U0001f680')
src = src.replace('\\U0001f50c', '\U0001f50c')
src = src.replace('\\U0001f6e1\\ufe0f', '\U0001f6e1\ufe0f')
src = src.replace('\\U0001f389', '\U0001f389')
src = src.replace('\\u2728', '\u2728')
src = src.replace('\\u0026', '&')

with open('build_release.py', 'w', encoding='utf-8') as f:
    f.write(src)

print("Fixed unicode escapes in release notes")
