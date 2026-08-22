"""Helper: locate findings whose title/category breaks reportlab Paragraph parsing."""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from database import db  # noqa: E402


async def main():
    docs = await db.findings.find({}, {"_id": 0, "id": 1, "title": 1, "category": 1,
                                       "platform": 1, "domain": 1}).to_list(5000)
    bad = [d for d in docs if any("<" in str(d.get(f) or "") or "&" in str(d.get(f) or "")
                                  for f in ("title", "category", "platform", "domain"))]
    print(f"total findings: {len(docs)}  suspect: {len(bad)}")
    for d in bad[:10]:
        print(d)


asyncio.run(main())
