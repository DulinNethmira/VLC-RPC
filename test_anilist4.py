import requests, json
query = '''
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id title { romaji english }
    coverImage { extraLarge large }
  }
}
'''
r = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': {'search': 'Super no Ura de Yani Suu Futari'}})
print(json.dumps(r.json(), indent=2))
