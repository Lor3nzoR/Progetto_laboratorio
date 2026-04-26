"""
Cache dei parsed_text precomputati per le entry del Gold Standard.

Scopo:
- evitare di riparsare ogni volta HTML molto grandi durante POST /parse su GS
  e GET /full_gs_eval;
- mantenere coerenza tra parse_from_html e full_gs_eval usando lo stesso
  output di parsing per l'identica entry GS.
"""

import hashlib
import json
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_FILE = PROJECT_ROOT / "gs_data" / "parsed_gs_cache.json"


def _make_key(domain: str, url: str, html_text: str) -> str:
    digest = hashlib.sha256(html_text.encode("utf-8")).hexdigest()
    return f"{domain.strip().lower()}|{url.strip()}|{digest}"


@lru_cache(maxsize=1)
def load_parsed_gs_cache() -> dict[str, dict]:
    """Carica la cache precomputata del GS, se presente."""
    if not CACHE_FILE.exists():
        return {}

    entries = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {
        _make_key(
            entry.get("domain", ""),
            entry.get("url", ""),
            entry.get("html_text", ""),
        ): entry
        for entry in entries
    }


def get_cached_parsed_entry(domain: str, url: str, html_text: str) -> dict | None:
    """Restituisce la entry cached corrispondente a dominio, URL e hash HTML."""
    return load_parsed_gs_cache().get(_make_key(domain, url, html_text))
