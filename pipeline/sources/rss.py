"""Parse an RSS or Atom feed into items."""
from __future__ import annotations

import calendar
import html
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup


@dataclass
class Item:
    id: str
    url: str
    dt: datetime
    title: str
    summary: str


def _text(fragment: str) -> str:
    return BeautifulSoup(fragment or "", "lxml").get_text(" ", strip=True)


def parse(xml: str) -> list[Item]:
    feed = feedparser.parse(xml)
    items: list[Item] = []
    for entry in feed.entries:
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        dt = (
            datetime.fromtimestamp(calendar.timegm(stamp), tz=timezone.utc)
            if stamp
            else datetime.now(timezone.utc)
        )
        link = entry.get("link", "")
        summary = entry.get("summary") or ""
        if not summary and entry.get("content"):
            summary = entry["content"][0].get("value", "")
        items.append(
            Item(
                id=entry.get("id") or link,
                url=link,
                dt=dt,
                title=html.unescape(_text(entry.get("title", ""))),
                summary=html.unescape(_text(summary)),
            )
        )
    return items
