import requests
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

print("Testing without custom User-Agent...")
try:
    r = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables})
    print(r.status_code, r.text[:100])
except Exception as e:
    print("Error:", e)

print("\nTesting with custom User-Agent...")
try:
    headers = {'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'}
    r = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables}, headers=headers)
    print(r.status_code, r.text[:100])
except Exception as e:
    print("Error:", e)
