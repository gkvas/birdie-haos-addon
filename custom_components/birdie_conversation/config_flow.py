"""Config flow for the Birdie Conversation integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_SECRET, CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN


async def _validate(hass, host: str, port: int) -> str | None:
    """Return None on success, or an error key on failure."""
    session = async_get_clientsession(hass)
    url = f"http://{host}:{port}/health"
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return "cannot_connect"
            data = await resp.json()
            if not data.get("ok"):
                return "cannot_connect"
    except Exception:  # noqa: BLE001 - any failure means unreachable
        return "cannot_connect"
    return None


class BirdieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Birdie Conversation config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            err = await _validate(
                self.hass, user_input[CONF_HOST], user_input[CONF_PORT]
            )
            if err:
                errors["base"] = err
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Birdie", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_API_SECRET): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
