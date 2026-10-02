import os
import json
import requests

PAGE_ID = "110527044555541"
API_VERSION = "v26.0"
ACCESS_TOKEN = os.environ["CLEP_FB_TOKEN"]

url = f"https://graph.facebook.com/{API_VERSION}/{PAGE_ID}/posts"

params = {
    "access_token": ACCESS_TOKEN,
    "fields": "id,message,created_time,permalink_url",
    "limit": 100,
}

posts = []
page = 1

while url:
    print(f"Descargando página {page}...")

    response = requests.get(
        url,
        params=params if page == 1 else None,
        timeout=30
    )
    response.raise_for_status()

    payload = response.json()
    batch = payload.get("data", [])

    posts.extend(batch)

    print(f"  {len(batch)} posts | acumulados: {len(posts)}")

    url = payload.get("paging", {}).get("next")
    params = None
    page += 1

posts = list({post["id"]: post for post in posts}.values())

posts.sort(
    key=lambda x: x.get("created_time", ""),
    reverse=True
)

output = os.path.expanduser("~/clep_facebook_posts.json")

with open(output, "w", encoding="utf-8") as f:
    json.dump(posts, f, ensure_ascii=False, indent=2)

print(f"\nTerminado: {len(posts)} publicaciones.")
print(f"Guardado en: {output}")
