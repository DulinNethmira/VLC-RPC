import re

def roman_to_int(s):
    rom_val = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    int_val = 0
    for i in range(len(s)):
        if i > 0 and rom_val[s[i]] > rom_val[s[i - 1]]:
            int_val += rom_val[s[i]] - 2 * rom_val[s[i - 1]]
        else:
            int_val += rom_val[s[i]]
    return int_val

def parse_filename(title: str):
    title = str(title or "")
    # Remove file extension and leading numbers (like "01. ")
    title = re.sub(r'^\d+[\.\-]\s+', '', title)
    title = re.sub(r'\.(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', title, flags=re.I).strip()
    title = re.sub(r'\s+(mp4|mkv|avi|flv|wmv|mov|webm|m4v|mpg|mpeg|ts|flac|mp3|wav|ogg|aac|m4a)$', '', title, flags=re.I).strip()
    
    # Remove fansub brackets like [SubsPlease] or [1080p]
    title = re.sub(r'\[.*?\]', '', title).strip()
    title = re.sub(r'\(.*?\)', '', title).strip()

    season = None
    episode = None

    # Match "Season 3 Episode 10" or "Season 3 Ep 10" or "S3 E10" or "S03E10"
    # and REMOVE it from title
    match_s_e = re.search(r'\b(?:S|Season)\s*(\d+)\s*(?:E|Ep|Episode)\s*(\d+)\b', title, re.I)
    if match_s_e:
        season = int(match_s_e.group(1))
        episode = int(match_s_e.group(2))
        title = title[:match_s_e.start()] + title[match_s_e.end():]
    else:
        # Match "Episode 10" or "E10" or "- 10" or just "10" at the end of the filename
        # But handle things like "One Piece E1175" -> E1175
        match_e = re.search(r'\b(?:E|Ep|Episode)\s*(\d+)\b', title, re.I)
        if match_e:
            episode = int(match_e.group(1))
            title = title[:match_e.start()] + title[match_e.end():]
        else:
            # Match strict trailing episode number like " - 12" or " 12"
            match_trailing_num = re.search(r'(?: - |\s+)(\d{1,4})$', title)
            if match_trailing_num:
                episode = int(match_trailing_num.group(1))
                title = title[:match_trailing_num.start()]

    title = title.replace('_', ' ').replace('.', ' ').strip()
    title = re.sub(r'\s+', ' ', title).strip()
    # Remove trailing hyphens
    title = re.sub(r'[\s\-]+$', '', title).strip()

    # Detect trailing roman numerals for season (e.g., "Overlord II" or "Overlord III")
    # BUT DO NOT REMOVE THEM FROM TITLE (per user request: title = "Overlord II", season = 2)
    match_roman = re.search(r'\b(I|II|III|IV|V|VI|VII|VIII|IX|X)$', title)
    if match_roman and season is None:
        season = roman_to_int(match_roman.group(1).upper())

    # Detect trailing "Season X" if episode was matched elsewhere
    match_trailing_season = re.search(r'\b(?:Season|S)\s*(\d+)$', title, re.I)
    if match_trailing_season and season is None:
        season = int(match_trailing_season.group(1))
        title = title[:match_trailing_season.start()].strip()

    title = re.sub(r'\s+', ' ', title).strip()
    
    return {
        "title": title,
        "season": season,
        "episode": episode
    }

print(parse_filename("Overlord II E10.mkv"))
print(parse_filename("One Piece E1175.mkv"))
print(parse_filename("Mushoku Tensei Jobless Reincarnation Season 3 Episode 10.mkv"))
print(parse_filename("Blood Blockade Battlefront S2E12.mkv"))
print(parse_filename("Re:ZERO -Starting Life in Another World- Season 4 Episode 15.mkv"))
print(parse_filename("[SubsPlease] Re:ZERO -Starting Life in Another World- Season 4 Episode 15 (1080p).mkv"))
