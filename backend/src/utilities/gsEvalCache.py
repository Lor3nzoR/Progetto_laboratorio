"""
Cache delle valutazioni aggregate di GET /full_gs_eval.

Scopo:
- evitare di ricalcolare metriche costose su testi molto lunghi, in
  particolare per le entry Wikipedia del Gold Standard;
- restituire rapidamente lo stesso payload finale che il backend
  produrrebbe aggregando parse + evaluate sul dominio.
"""

import json
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_FILE = PROJECT_ROOT / "gs_data" / "full_gs_eval_cache.json"


@lru_cache(maxsize=1)
def load_full_gs_eval_cache() -> dict[str, dict]:
    """Carica da disco le metriche aggregate precomputate, se disponibili."""
    if not CACHE_FILE.exists():
        return {}

    entries = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {
        str(entry.get("domain", "")).strip().lower(): entry.get("evaluation", {})
        for entry in entries
        if entry.get("domain")
    }


def get_cached_full_gs_eval(domain: str) -> dict | None:
    """Restituisce la valutazione aggregate cached per il dominio richiesto."""
    return load_full_gs_eval_cache().get(domain.strip().lower())
