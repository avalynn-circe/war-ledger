"""Translate Cyrillic excerpts to English once, and keep them.

The cache (data/translations.json) maps a hash of the source text to its
English rendering, so a string is sent to the model once. Without an API
key the cache is still applied, and strings not in it stay in the original.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import re

log = logging.getLogger(__name__)

CYRILLIC = re.compile(r"[\u0400-\u04FF]")
MODEL = "claude-opus-5-5"
CHUNK = 25
SYSTEM = (
    "You translate short excerpts of Ukrainian and Russian military and news reporting into plain English. "
    "Keep every number, date, unit name and weapon designation exactly as written. "
    "Transliterate place names: Ukrainian national system for Ukrainian text, BGN/PCGN for Russian text; "
    "keep words already in English as they are. Preserve emoji and list punctuation. "
    "Return only a JSON array of strings, one per input string, in the same order and of the same length. No commentary."
)


def needs(text: str | None) -> bool:
    return bool(text) and bool(CYRILLIC.search(text))


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def make_client():
    """An Anthropic client when a key is configured, else None."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic package not installed; translations skipped")
        return None
    return anthropic.Anthropic()


class Translator:
    def __init__(self, cache_path: pathlib.Path, client=None):
        self.path = pathlib.Path(cache_path)
        self.client = client
        self.cache: dict[str, str] = {}
        if self.path.exists():
            self.cache = json.loads(self.path.read_text(encoding="utf-8"))
        self.dirty = False

    def save(self) -> None:
        if self.dirty:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")

    def _call(self, chunk: list[str]) -> list[str] | None:
        resp = self.client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": json.dumps(chunk, ensure_ascii=False)}],
        )
        if resp.stop_reason == "refusal":
            log.warning("translation refused for a chunk of %d strings", len(chunk))
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        try:
            out = json.loads(text)
        except json.JSONDecodeError:
            log.warning("translation response was not JSON")
            return None
        if not isinstance(out, list) or len(out) != len(chunk) or not all(isinstance(x, str) for x in out):
            log.warning("translation response had the wrong shape")
            return None
        return out

    def translate_many(self, strings: list[str]) -> None:
        missing = [s for s in dict.fromkeys(strings) if s and _key(s) not in self.cache]
        if not missing or self.client is None:
            return
        for i in range(0, len(missing), CHUNK):
            chunk = missing[i : i + CHUNK]
            try:
                out = self._call(chunk)
            except Exception as exc:  # the site must build even when the API does not answer
                log.warning("translation call failed: %s", exc)
                return
            if out is None:
                continue
            for src, en in zip(chunk, out):
                self.cache[_key(src)] = en
                self.dirty = True

    def apply(self, events: list) -> int:
        """Set quote_en, detail_en and locations_en on events whose text is Cyrillic."""
        wanted: list[str] = []
        for e in events:
            for text in [e.quote, e.detail, *e.locations]:
                if needs(text):
                    wanted.append(text)
        self.translate_many(wanted)
        done = 0
        for e in events:
            if needs(e.quote) and _key(e.quote) in self.cache:
                e.quote_en = self.cache[_key(e.quote)]
                done += 1
            if needs(e.detail) and _key(e.detail) in self.cache:
                e.detail_en = self.cache[_key(e.detail)]
            if any(needs(x) for x in e.locations):
                e.locations_en = [self.cache.get(_key(x), x) if needs(x) else x for x in e.locations]
        return done
