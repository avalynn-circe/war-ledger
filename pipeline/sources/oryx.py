"""Oryx equipment-loss pages: keep only the heading lines that carry totals.

The page is several megabytes of photo links; the counts live in <h3>
headings such as "Russia - 21964, of which: destroyed: 16321, ..." and
"Tanks (4000, of which destroyed: 2800, damaged: 150, ...)". One Post per
fetch day holds those lines, so the raw archive stays small.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from .telegram import Post

TOTAL = re.compile(r"^(Russia|Ukraine)\s*[-–—]\s*\d")
CATEGORY = re.compile(r"^[A-Z][A-Za-z0-9 &'()/,.-]*\(\d[\d,]*,\s*of which", re.I)


def parse(html: str, source: dict) -> list[Post]:
    soup = BeautifulSoup(html, "lxml")
    lines: list[str] = []
    for h in soup.find_all(["h3", "h2", "h4"]):
        text = " ".join(h.get_text(" ", strip=True).split())
        if TOTAL.match(text) or CATEGORY.match(text):
            lines.append(text)
    if not lines:
        return []
    now = datetime.now(timezone.utc)
    return [Post(id=f"{source['id']}-{now.date().isoformat()}", url=source["url"], dt=now, text="\n".join(lines))]
