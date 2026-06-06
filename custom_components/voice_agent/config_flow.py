"""Config flow for Voice Agent Router."""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_ROUTER_API_KEY,
    CONF_ROUTER_URL,
    CONF_SATELLITE_MAP,
    DEFAULT_ROUTER_URL,
    DOMAIN,
)


class VoiceAgentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                satellite_map = json.loads(user_input.get(CONF_SATELLITE_MAP) or "{}")
                if not isinstance(satellite_map, dict):
                    raise ValueError("satellite map must be a JSON object")
            except ValueError:
                errors[CONF_SATELLITE_MAP] = "invalid_json"
            else:
                return self.async_create_entry(
                    title="Voice Agent Router",
                    data={
                        CONF_ROUTER_URL: user_input[CONF_ROUTER_URL].rstrip("/"),
                        CONF_ROUTER_API_KEY: user_input.get(CONF_ROUTER_API_KEY, ""),
                        CONF_SATELLITE_MAP: satellite_map,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ROUTER_URL, default=DEFAULT_ROUTER_URL): str,
                vol.Optional(CONF_ROUTER_API_KEY, default=""): str,
                vol.Optional(CONF_SATELLITE_MAP, default="{}"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
