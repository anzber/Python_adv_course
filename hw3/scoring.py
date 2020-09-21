import hashlib
import json

def key_from_parts(phone, birthday, first_name, last_name):
    key_parts = [
        first_name or "",
        last_name or "",
        str(phone) if phone else "",
        birthday or "",
    ]
    return "uid:" + hashlib.md5("".join(key_parts).encode('utf-8')).hexdigest()


def get_score(store,  phone=None, email=None, birthday=None, gender=None, first_name=None, last_name=None):
    key = key_from_parts(phone=phone, birthday=birthday, first_name=first_name, last_name=last_name)
    # try get from cache,
    # fallback to heavy calculation in case of cache miss
    score = store.cache_get(key) or 0
    if score:
        return score
    if phone:
        score += 1.5
    if email:
        score += 1.5
    if birthday and gender:
        score += 1.5
    if first_name and last_name:
        score += 0.5
    # cache for 60 minutes
    store.cache_set(key, score, 60 * 60)
    return score


def get_interests(store, cid):
    return store.get(cid)
