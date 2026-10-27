"""HTTP fetching, with an offline mode that reads recorded fixtures."""
from __future__ import annotations

import logging
import pathlib
import time

import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; war-ledger/0.1; "
    "+https://github.com/avalynn-circe/war-ledger)"
)
EXT = {"telegram": "html", "rss": "xml", "html": "html"}


class Fetcher:
    def __init__(self, offline_dir: str | None = None, timeout: int = 30, retries: int = 3):
        self.offline_dir = pathlib.Path(offline_dir) if offline_dir else None
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def get(self, source: dict) -> str | None:
        """Return the page body for a source, or None when it cannot be read."""
        if self.offline_dir:
            path = self.offline_dir / f"{source['id']}.{EXT.get(source['kind'], 'txt')}"
            if not path.exists():
                log.warning("%s: no fixture at %s", source["id"], path)
                return None
            return path.read_text(encoding="utf-8")

        delay = 2
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(source["url"], timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as exc:
                log.warning("%s: attempt %d failed: %s", source["id"], attempt, exc)
                if attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
        return None
