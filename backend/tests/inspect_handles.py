"""Read-only inspection of odd usernames in Welspun social findings."""
import asyncio
import os
from collections import Counter

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
TID = "6bd8b86e-a6f4-492d-96d3-db66b5ef7d2d"

SUSPECT = {"popular", "hashtag", "explore", "feed", "search", "tags", "share",
           "help", "about", "login", "signup", "results", "hashtags", "posts",
           "in", "company", "channel", "user", "r", "u", "watch", "p", "reel"}


async def main():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    docs = await db.findings.find({"tenant_id": TID, "module": "social"}, {"_id": 0}).to_list(1000)
    print("total:", len(docs))
    print("content_type:", Counter((d.get("entities") or {}).get("content_type") for d in docs))
    print("platform:", Counter(d.get("platform") for d in docs))
    print("\n--- suspect / non-handle usernames ---")
    for d in docs:
        u = ((d.get("entities") or {}).get("username") or "")
        if u.lower() in SUSPECT or not u:
            print(f"{d['platform']:10} | {u!r:28} | {d['url'][:110]}")
    print("\n--- LinkedIn samples ---")
    for d in docs:
        if d.get("platform") == "LinkedIn":
            e = d["entities"]
            print(f"{e.get('username')!r:40} ct={e.get('content_type'):8} | {d['url'][:110]}")
    print("\n--- usernames with suspicious length/chars ---")
    for d in docs:
        u = ((d.get("entities") or {}).get("username") or "")
        if len(u) > 40 or " " in u:
            print(f"{d['platform']:10} | {u!r} | {d['url'][:100]}")
    c.close()


asyncio.run(main())
