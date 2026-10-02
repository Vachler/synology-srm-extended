"""Build-time translation drafts. Sends only static UI text; never runtime/router data."""

import concurrent.futures
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components/synology_srm_extended"
LANGS = [
    "en",
    "de",
    "sk",
    "pl",
    "fr",
    "es",
    "hu",
    "nl",
    "pt",
    "pt-BR",
    "ro",
    "uk",
    "ru",
    "tr",
    "el",
    "ja",
    "ko",
    "zh-Hans",
    "zh-Hant",
    "vi",
    "th",
    "id",
    "ms",
    "hi",
    "ar",
    "he",
    "it",
]
config = json.loads((ROOT / "translations/cs.json").read_text(encoding="utf-8"))
frontend = json.loads((ROOT / "frontend/locales/cs.json").read_text(encoding="utf-8"))


def leaves(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from leaves(value)
    else:
        yield obj


texts = list(dict.fromkeys([*leaves(config), *frontend.values()]))


def request(text, lang):
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "cs",
            "tl": {"zh-Hans": "zh-CN", "zh-Hant": "zh-TW"}.get(lang, lang),
            "dt": "t",
            "q": text,
        }
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(
                "https://translate.googleapis.com/translate_a/single?" + query, timeout=35
            ) as response:
                data = json.load(response)
            return "".join(part[0] or "" for part in data[0])
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 + attempt)


def translated(values, lang):
    # Protected placeholders cannot change names or disappear.
    tokens = {}

    def protect(m):
        token = "ZXQ" + str(len(tokens)) + "QXZ"
        tokens[token] = m.group()
        return token

    joined = "\n".join(re.sub(r"\{[^{}]+\}", protect, v) for v in values)
    out = request(joined, lang).split("\n")
    if len(out) != len(values):
        if len(values) == 1:
            raise ValueError("Unexpected line split")
        return [translated([value], lang)[0] for value in values]
    for i, text in enumerate(out):
        for token, value in tokens.items():
            text = text.replace(token, value)
        if set(re.findall(r"\{[^{}]+\}", text)) != set(re.findall(r"\{[^{}]+\}", values[i])):
            # Individual retries avoid cross-line placeholder reordering.
            if len(values) > 1:
                return [translated([value], lang)[0] for value in values]
            raise ValueError("Placeholder mismatch " + lang)
        out[i] = text.strip()
    return out


def work(lang):
    cache = ROOT.parent.parent / "tools" / f"translation-cache-{lang}.json"
    mapped = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    pending = [v for v in texts if v not in mapped]
    batches = []
    batch = []
    size = 0
    for value in pending:
        if size + len(value) > 2200 and batch:
            batches.append(batch)
            batch = []
            size = 0
        batch.append(value)
        size += len(value) + 1
    if batch:
        batches.append(batch)
    for batch in batches:
        mapped.update(zip(batch, translated(batch, lang), strict=True))
        cache.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")

    def convert(obj):
        return {k: convert(v) for k, v in obj.items()} if isinstance(obj, dict) else mapped[obj]

    draft = ROOT.parent.parent / "tools" / "translation-drafts"
    (draft / "ha").mkdir(parents=True, exist_ok=True)
    (draft / "frontend").mkdir(parents=True, exist_ok=True)
    (draft / "ha" / f"{lang}.json").write_text(
        json.dumps(convert(config), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (draft / "frontend" / f"{lang}.json").write_text(
        json.dumps(convert(frontend), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(lang, "complete", flush=True)


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for _result in pool.map(work, LANGS):
            pass
