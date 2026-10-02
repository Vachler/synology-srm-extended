"""Complete offline translations and placeholder contracts."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components/synology_srm_extended"
LANGUAGES = set(
    (
        "cs en de sk pl fr es hu nl pt pt-BR ro uk ru tr el ja ko "
        "zh-Hans zh-Hant vi th id ms hi ar he it"
    ).split()
)


def flatten(obj, prefix=""):
    result = {}
    for key, value in obj.items():
        path = prefix + "/" + key
        if isinstance(value, dict):
            result.update(flatten(value, path))
        else:
            result[path] = value
    return result


def test_all_locales_have_matching_keys_and_placeholders():
    for folder in ("translations", "frontend/locales"):
        files = list((ROOT / folder).glob("*.json"))
        assert {p.stem for p in files} == LANGUAGES
        reference = flatten(json.loads((ROOT / folder / "cs.json").read_text(encoding="utf-8")))
        for path in files:
            entries = flatten(json.loads(path.read_text(encoding="utf-8")))
            assert entries.keys() == reference.keys(), path
            for key, value in entries.items():
                assert isinstance(value, str) and value.strip(), (path, key)
                assert sorted(re.findall(r"\{\w+\}", value)) == sorted(
                    re.findall(r"\{\w+\}", reference[key])
                ), (path, key)


def test_english_is_the_native_fallback():
    assert json.loads((ROOT / "strings.json").read_text(encoding="utf-8")) == json.loads(
        (ROOT / "translations/en.json").read_text(encoding="utf-8")
    )
