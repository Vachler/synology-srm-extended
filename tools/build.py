"""Vytvoří čistý instalační ZIP bez testů, prostředí a diagnostických dat."""

import runpy
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    runpy.run_path(str(ROOT / "tools" / "build_localization.py"))
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    output = dist / "synology_srm_extended-0.1.12.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        component = ROOT / "custom_components" / "synology_srm_extended"
        for path in sorted(component.rglob("*")):
            if path.suffix in (".py", ".json", ".png", ".js") and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ROOT))
        for relative in ("README.md", "docs/API.md", "docs/BRAND.md", "tools/probe.py"):
            archive.write(ROOT / relative, relative)
    print(output)


if __name__ == "__main__":
    main()
