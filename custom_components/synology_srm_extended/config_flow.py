"""Konfigurace přes UI; heslo se neposílá do diagnostiky ani logů."""

from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_OPTIONS, DOMAIN
from .runtime import create_client
from .srm.connection import normalize_host
from .srm.errors import (
    AuthenticationError,
    CertificateError,
    PermissionDenied,
    ResponseError,
    SrmError,
    TwoFactorRequired,
    UnsupportedError,
)
from .srm.models import parse_clients


def connection_schema(defaults: dict | None = None) -> vol.Schema:
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required("host", default=values.get("host", "")): str,
            vol.Required("port", default=values.get("port", 8001)): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=65535),
            ),
            vol.Required("https", default=values.get("https", True)): bool,
            vol.Required("verify_ssl", default=values.get("verify_ssl", True)): bool,
            vol.Required("username", default=values.get("username", "")): str,
            # Heslo nikdy nepředvyplňujeme při chybě ani rekonfiguraci.
            vol.Required("password"): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        }
    )


async def validate_connection(hass, data: dict) -> str | None:
    try:
        data["host"] = normalize_host(data["host"])
    except ValueError:
        return "invalid_host"
    api, session = create_client(hass, data)
    try:
        parse_clients(await api.read("clients"))
    except TwoFactorRequired:
        return "two_factor_required"
    except AuthenticationError:
        return "invalid_auth"
    except PermissionDenied:
        return "permission_denied"
    except CertificateError:
        return "invalid_certificate"
    except UnsupportedError:
        return "unsupported_api"
    except ResponseError:
        return "unsupported_response"
    except SrmError:
        return "cannot_connect"
    finally:
        try:
            await api.logout()
        finally:
            session.detach()
    return None


class SrmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            if error := await validate_connection(self.hass, user_input):
                errors["base"] = error
            else:
                await self.async_set_unique_id(uuid4().hex)
                return self.async_create_entry(title="Synology RT6600ax", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=connection_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._edit_connection("reauth_confirm", user_input, self._get_reauth_entry())

    async def async_step_reconfigure(self, user_input=None):
        return await self._edit_connection("reconfigure", user_input, self._get_reconfigure_entry())

    async def _edit_connection(self, step_id, user_input, entry):
        errors = {}
        if user_input is not None:
            if error := await validate_connection(self.hass, user_input):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id=step_id,
            data_schema=connection_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SrmOptionsFlow()


class SrmOptionsFlow(config_entries.OptionsFlowWithReload):
    async def async_step_init(self, user_input=None):
        values = {**DEFAULT_OPTIONS, **self.config_entry.options}
        runtime = getattr(self.config_entry, "runtime_data", None)
        known = dict(runtime.clients.inventory.known) if runtime else {}
        for mac in values["tracker_clients"] + values["client_entities"]:
            known.setdefault(mac, mac)
        choices = [
            {"value": mac, "label": f"{name} ({mac})"} for mac, name in sorted(known.items())
        ]
        if user_input is not None:
            # Výběr je uzavřený na známé identity; prázdný výběr znamená žádné trackery.
            selected = [m for m in user_input.get("tracker_clients", []) if m in known]
            clients = [m for m in user_input.get("client_entities", []) if m in known]
            return self.async_create_entry(
                title="",
                data={
                    **user_input,
                    "create_trackers": bool(selected),
                    "tracker_clients": selected,
                    "client_entities": clients,
                },
            )
        schema = {
            vol.Required("poll_interval", default=values["poll_interval"]): vol.All(
                vol.Coerce(int),
                vol.Range(min=5, max=3600),
            ),
            vol.Required("create_clients", default=values["create_clients"]): bool,
            vol.Optional("client_entities", default=values["client_entities"]): SelectSelector(
                SelectSelectorConfig(options=choices, multiple=True),
            ),
            vol.Optional("tracker_clients", default=values["tracker_clients"]): SelectSelector(
                SelectSelectorConfig(options=choices, multiple=True),
            ),
            vol.Required(
                "traffic_source_unit", default=values["traffic_source_unit"]
            ): SelectSelector(
                SelectSelectorConfig(
                    options=["unknown", "B/s", "KB/s", "KiB/s", "bit/s"],
                    translation_key="traffic_source_unit",
                ),
            ),
            vol.Required(
                "traffic_rx_direction", default=values["traffic_rx_direction"]
            ): SelectSelector(
                SelectSelectorConfig(
                    options=["unknown", "download", "upload"],
                    translation_key="traffic_rx_direction",
                ),
            ),
            vol.Required("remove_unselected", default=values["remove_unselected"]): bool,
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
