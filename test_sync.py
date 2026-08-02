import re, requests

def _normalize(text):
    if not text: return ''
    return re.sub(r'[^\w\s]', ' ', text).strip().lower()

search = 'You and I Are Polar Opposites'
search_normalized = _normalize(re.sub(r'\s*\(\d{4}\)', '', search))
search_compact = re.sub(r'\s+', '', search_normalized)
print('Search compact:', search_compact)

# Check what AniList returns for the page search
r = requests.post('https://graphql.anilist.co', json={
    'query': '''query($search: String, $type: MediaType) {
        Page(perPage: 5) {
            media(search: $search, type: $type) {
                id episodes format
                title { romaji english }
            }
        }
    }''',
    'variables': {'search': search_normalized, 'type': 'ANIME'}
}, headers={'Content-Type': 'application/json'}, timeout=8)

data = r.json()
print('Status:', r.status_code)
for m in (data.get('data') or {}).get('Page', {}).get('media', []):
    t = m.get('title', {})
    title = t.get('english') or t.get('romaji')
    print(f"  Result: '{title}' | ID: {m['id']} | eps: {m.get('episodes')} | format: {m.get('format')}")
    
    # Simulate the _match function with One Piece
    for test_title in ['One Piece', 'Wan Pisu']:
        c = _normalize(test_title)
        c_compact = re.sub(r'\s+', '', c)
        match = search_compact in c_compact or c_compact in search_compact
        if match:
            print(f"    !! MATCHES '{test_title}' compact='{c_compact}'")
