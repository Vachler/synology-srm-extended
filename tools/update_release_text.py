"""Aktualizace českých textů vydání 0.1.1."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
component = root / "custom_components" / "synology_srm_extended"
path = component / "strings.json"
data = json.loads(path.read_text(encoding="utf-8"))
data["config"]["step"]["user"]["description"] = (
    "Vytvoří se pouze zařízení routeru se souhrny a seznamem klientů. "
    "Samostatné klientské entity ani trackery se automaticky nepřidají. "
    "Integrace pouze čte stav; HTTPS a ověření certifikátu jsou doporučené."
)
step = data["options"]["step"]["init"]
step["title"] = "Klienti pod routerem"
step["description"] = (
    "Všichni klienti jsou v seznamu u routeru. Samostatné entity připojení můžete "
    "volitelně vybrat níže; i ty zůstanou pod routerem. Trackery jsou nezávislé a volitelné."
)
step["data"].pop("include_offline", None)
step["data_description"].pop("include_offline", None)
step["data"]["create_clients"] = "Povolit vybrané entity připojení pod routerem"
step["data"]["client_entities"] = "Klienti se samostatnou entitou připojení"
step["data"]["remove_unselected"] = "Odstranit nevybrané klientské entity této integrace"
step["data_description"]["client_entities"] = (
    "Prázdný výběr nevytvoří žádné klientské entity. Seznam všech klientů zůstane u routeru."
)
step["data_description"]["remove_unselected"] = (
    "Uklidí také entity automaticky vytvořené verzí 0.1.0. "
    "Odstraní nevybrané entity a jejich nastavení z registru HA; "
    "jejich automatizace bude případně nutné upravit. Router ani jiné integrace neodstraní."
)
data["entity"]["binary_sensor"]["client_connected"]["name"] = "{client} – připojení"
data["entity"]["device_tracker"]["presence"]["name"] = "{client} – přítomnost"
for dest in (path, component / "translations/cs.json", component / "translations/en.json"):
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
