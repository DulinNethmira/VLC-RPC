import requests, json
query = '''
query ($search: String) {
  Page(page: 1, perPage: 10) {
    media(search: $search, type: ANIME) {
      id title { romaji english }
      coverImage { extraLarge large }
    }
  }
}
'''
r = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': {'search': 'Smoking Behind The Supermarket With You E9'}})
print(json.dumps(r.json(), indent=2))
