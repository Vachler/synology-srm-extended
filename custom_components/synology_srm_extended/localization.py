"""Local device-name defaults; runtime translation never uses an external service."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=32)
def device_labels(language):
    folder = Path(__file__).parent / "frontend" / "locales"
    available = {p.stem.lower(): p for p in folder.glob("*.json")}
    key = (language or "en").replace("_", "-").lower()
    key = {"zh-cn": "zh-hans", "zh-tw": "zh-hant", "zh-hk": "zh-hant", "iw": "he"}.get(key, key)
    path = available.get(key) or available.get(key.split("-")[0]) or available["en"]
    labels = json.loads(path.read_text(encoding="utf-8"))
    return labels["Integrovaní klienti"], labels["Klienti routeru"]
