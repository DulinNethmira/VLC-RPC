import os

filepath = 'vlc_discord_rpc_gui.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

target = """        query = \"\"\"
        query {
          Page(page: 1, perPage: 15) {
            airingSchedules(notYetAired: true, sort: TIME) {
              episode
              airingAt
              media {
                title { romaji english }
                coverImage { medium }
                isAdult
              }
            }
          }
        }
        \"\"\"
        try:
            headers = {'Authorization': 'Bearer ' + token}
            import requests
            headers["User-Agent"] = "VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)"
            r = requests.post('https://graphql.anilist.co', json={'query': query}, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                items = data.get("data", {}).get("Page", {}).get("airingSchedules", [])
                results = []
                for item in items:
                    media = item.get("media")
                    if media and not media.get("isAdult"):
                        results.append({
                            "title": media.get("title"),
                            "coverImage": media.get("coverImage"),
                            "nextAiringEpisode": {
                                "episode": item.get("episode"),
                                "airingAt": item.get("airingAt"),
                                "timeUntilAiring": item.get("airingAt") - int(time.time())
                            }
                        })
                self._cached_airing_schedule = {"status": "ok", "items": results}
                self._cached_airing_time = time.time()
                return self._cached_airing_schedule
            else:"""

replacement = """        query = \"\"\"
        query($userName: String) {
          MediaListCollection(userName: $userName, type: ANIME, status: CURRENT) {
            lists {
              entries {
                media {
                  id
                  title { romaji english }
                  coverImage { medium }
                  isAdult
                  nextAiringEpisode {
                    episode
                    airingAt
                    timeUntilAiring
                  }
                }
              }
            }
          }
        }
        \"\"\"
        try:
            headers = {'Authorization': 'Bearer ' + token}
            import requests
            headers["User-Agent"] = "VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)"
            r = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': {'userName': userName}}, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                lists = data.get("data", {}).get("MediaListCollection", {}).get("lists", [])
                results = []
                seen_media_ids = set()
                
                for lst in lists:
                    for entry in lst.get("entries", []):
                        media = entry.get("media")
                        if media and not media.get("isAdult") and media.get("nextAiringEpisode"):
                            media_id = media.get("id")
                            if media_id in seen_media_ids:
                                continue
                            seen_media_ids.add(media_id)
                            
                            nex = media["nextAiringEpisode"]
                            title_obj = media.get("title", {})
                            results.append({
                                "title": title_obj.get("english") or title_obj.get("romaji"),
                                "coverImage": media.get("coverImage"),
                                "nextAiringEpisode": {
                                    "episode": nex.get("episode"),
                                    "airingAt": nex.get("airingAt"),
                                    "timeUntilAiring": nex.get("timeUntilAiring")
                                }
                            })
                
                # Sort by timeUntilAiring
                results.sort(key=lambda x: x["nextAiringEpisode"]["timeUntilAiring"])
                self._cached_airing_schedule = {"status": "ok", "items": results}
                self._cached_airing_time = time.time()
                return self._cached_airing_schedule
            else:"""

if target in content:
    content = content.replace(target, replacement)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
else:
    print("Target string not found in the file.")
