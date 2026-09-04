import urllib.request
import json

query = '''
query ($search: String) {
  Media (search: $search, type: ANIME) {
    id
    title { romaji english native }
  }
}
'''

variables = {'search': 'That Time I Got Reincarnated As A Slime'}
url = 'https://graphql.anilist.co'
data = json.dumps({'query': query, 'variables': variables}).encode('utf-8')
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

try:
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print('Error:', e)
    if hasattr(e, 'read'):
        print('Body:', e.read().decode('utf-8', errors='ignore'))
