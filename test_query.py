import requests, json
query = '''
query ($search: String) {
    Page(page: 1, perPage: 10) {
        media(search: $search, type: ANIME) {
            id title { romaji english } format episodes
        }
    }
}
'''
r = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': {'search': 'Blood Blockade Battlefront King of Kings Restaurant Fit for a King'}})
with open('test_query_out.json', 'w', encoding='utf-8') as f:
    json.dump(r.json(), f, indent=2)
