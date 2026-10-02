"""Izolované testy knihovny: nenačítají ani nepředstírají Home Assistant."""

import sys
from pathlib import Path
from types import ModuleType

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "synology_srm_extended"
sys.path.insert(0, str(COMPONENT))

# Transport lze testovat bez spuštění HA __init__. Nejde o náhradu HA runtime.
package = ModuleType("component_under_test")
package.__path__ = [str(COMPONENT)]
sys.modules[package.__name__] = package
