import json

cache = {}

def persist_rewatch_state(key_or_id, watch_mode, rewatch_number, identity, title):
    keys = [str(key_or_id)]
    if identity.get("anilist_id"):
        keys.append(str(identity["anilist_id"]))
    if identity.get("source_key"):
        keys.append(str(identity["source_key"]))
    if identity.get("normalized_title"):
        keys.append(str(identity["normalized_title"]))
    if title:
        keys.append(str(title))

    for k in set(keys):
        if k:
            cache[k] = {
                "watch_mode": watch_mode,
                "rewatch_number": rewatch_number
            }

def lookup_rewatch_state(identity, title):
    candidate_keys = []
    if identity.get("anilist_id"):
        candidate_keys.append(str(identity["anilist_id"]))
    if identity.get("source_key"):
        candidate_keys.append(str(identity["source_key"]))
    if identity.get("normalized_title"):
        candidate_keys.append(str(identity["normalized_title"]))
    if title:
        candidate_keys.append(str(title))

    for k in candidate_keys:
        res = cache.get(k)
        if res and res.get("watch_mode") == "REWATCH":
            return res
    return None

# Test offline / 403 identity (anilist_id is None)
identity = {
    "source_key": "Mushoku Tensei: Jobless Reincarnation",
    "source_title": "Mushoku Tensei: Jobless Reincarnation",
    "title": "Mushoku Tensei: Jobless Reincarnation",
    "anilist_id": None,
    "normalized_title": "mushoku tensei jobless reincarnation",
    "state": "LOCAL_VALIDATED",
}

# 1. User starts rewatch in local mode
persist_rewatch_state("mushoku tensei jobless reincarnation", "REWATCH", 1, identity, "Mushoku Tensei: Jobless Reincarnation")

# 2. Verify lookup succeeds even when anilist_id is None
found = lookup_rewatch_state(identity, "Mushoku Tensei: Jobless Reincarnation")
print("Lookup result when anilist_id is None:", found)
assert found is not None and found["watch_mode"] == "REWATCH"
print("SUCCESS: Local rewatch state lookup verified!")
