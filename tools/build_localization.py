import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
component = root / "custom_components/synology_srm_extended"
data = {
    p.stem: json.loads(p.read_text(encoding="utf-8"))
    for p in sorted((component / "frontend/locales").glob("*.json"))
}
p = component / "frontend/clients.js"
s = p.read_text(encoding="utf-8")
marker = "// END GENERATED LOCALIZATION\n"
if marker in s:
    s = s.split(marker, 1)[1]
p.write_text(
    "// BEGIN GENERATED LOCALIZATION\nconst SRM_TRANSLATIONS = "
    + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    + ";\n"
    + (root / "tools/localization_runtime.js").read_text(encoding="utf-8-sig")
    + "\n"
    + marker
    + s,
    encoding="utf-8",
)
print("Embedded locales:", len(data))
