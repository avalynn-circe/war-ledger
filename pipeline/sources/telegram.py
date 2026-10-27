"""Parse the public web preview of a Telegram channel (https://t.me/s/<channel>)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from bs4 import BeautifulSoup


@dataclass
class Post:
    id: str
    url: str
    dt: datetime
    text: str


def parse(html: str) -> list[Post]:
    soup = BeautifulSoup(html, "lxml")
    posts: list[Post] = []
    for node in soup.select("div.tgme_widget_message"):
        ref = node.get("data-post")
        body = node.select_one("div.tgme_widget_message_text")
        if not ref or body is None:
            continue
        for br in body.find_all("br"):
            br.replace_with("\n")
        text = "\n".join(line.strip() for line in body.get_text().splitlines()).strip()
        dt = datetime.now(timezone.utc)
        time_node = node.select_one("a.tgme_widget_message_date time")
        if time_node is not None and time_node.get("datetime"):
            dt = datetime.fromisoformat(time_node["datetime"].replace("Z", "+00:00"))
        posts.append(Post(id=ref, url=f"https://t.me/{ref}", dt=dt, text=text))
    return posts
