import requests
import json

url = "https://graphql.anilist.co"
query = """
query ($search: String) {
    Media(search: $search, type: ANIME) {
        id
        title {
            romaji
            english
        }
    }
}
"""
variables = {"search": "Mushoku Tensei"}

uas = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 VLC-RPC/6.2.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"
]

for ua in uas:
    headers = {
        "User-Agent": ua,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        r = requests.post(url, json={"query": query, "variables": variables}, headers=headers, timeout=10)
        print(f"UA: {ua[:40]}... -> Status: {r.status_code}")
        if r.status_code != 200:
            print("Response:", r.text[:200])
    except Exception as e:
        print("Error:", e)
