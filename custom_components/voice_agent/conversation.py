"""Conversation entity that forwards turns to the router service."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ROUTER_API_KEY, CONF_ROUTER_URL, CONF_SATELLITE_MAP, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([VoiceAgentConversationEntity(hass, entry)])


class VoiceAgentConversationEntity(conversation.ConversationEntity):
    _attr_name = "Voice Agent Router"
    _attr_unique_id = "voice_agent_router"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

    @property
    def supported_languages(self) -> list[str] | str:
        """Return supported languages."""

        return "*"

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        language = getattr(user_input, "language", "en")
        conversation_id = getattr(chat_log, "conversation_id", None)
        agent_id = getattr(user_input, "agent_id", self.entity_id)
        device_id = getattr(user_input, "device_id", None)

        try:
            satellite_entity_id = self._resolve_satellite_entity_id(device_id)
            area_id = self._resolve_area_id(device_id)
            payload = {
                "text": user_input.text,
                "language": language,
                "conversation_id": conversation_id,
                "ha_device_id": device_id,
                "assist_satellite_entity_id": satellite_entity_id,
                "area_id": area_id,
                "area_name": self._area_name(area_id),
                "reply_target": {
                    "channel": "assist_satellite" if satellite_entity_id else "none",
                    "entity_id": satellite_entity_id,
                    "device_id": device_id,
                },
                "metadata": {
                    "agent_id": agent_id,
                    "integration": DOMAIN,
                    "home_assistant": self._home_assistant_snapshot(),
                },
            }
            result = await self._post_to_router(payload)
            response_text = result.get("response_text") or "I couldn't complete that."
        except Exception:  # noqa: BLE001 - HA should get a graceful response.
            _LOGGER.exception("Voice Agent Router request failed")
            response_text = "I couldn't reach the voice agent router."

        self._add_assistant_content(chat_log, agent_id, response_text)

        response = intent.IntentResponse(language=language)
        response.async_set_speech(response_text)
        return conversation.ConversationResult(
            response=response,
            conversation_id=conversation_id,
            continue_conversation=False,
        )

    async def _post_to_router(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        router_url = self.entry.data[CONF_ROUTER_URL]
        headers = {}
        router_api_key = self.entry.data.get(CONF_ROUTER_API_KEY)
        if router_api_key:
            headers["Authorization"] = f"Bearer {router_api_key}"
        async with session.post(
            f"{router_url}/v1/voice/handle",
            json=payload,
            headers=headers,
            timeout=30,
        ) as response:
            if response.status >= 400:
                body = await response.text()
                _LOGGER.warning(
                    "Voice Agent Router returned HTTP %s: %s",
                    response.status,
                    body[:500],
                )
            response.raise_for_status()
            return await response.json()

    def _add_assistant_content(
        self,
        chat_log: conversation.ChatLog,
        agent_id: str | None,
        response_text: str,
    ) -> None:
        add_content = getattr(chat_log, "async_add_assistant_content_without_tools", None)
        assistant_content = getattr(conversation, "AssistantContent", None)
        if add_content is None or assistant_content is None or not agent_id:
            return
        add_content(assistant_content(agent_id=agent_id, content=response_text))

    def _resolve_satellite_entity_id(self, device_id: str | None) -> str | None:
        if not device_id:
            return None

        satellite_map: dict[str, str] = self.entry.data.get(CONF_SATELLITE_MAP, {})
        if mapped_entity_id := satellite_map.get(device_id):
            return mapped_entity_id

        entity_registry = er.async_get(self.hass)
        matches = [
            entry.entity_id
            for entry in entity_registry.entities.values()
            if entry.device_id == device_id and entry.entity_id.startswith("assist_satellite.")
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _resolve_area_id(self, device_id: str | None) -> str | None:
        if not device_id:
            return None

        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get(device_id)
        if device_entry and device_entry.area_id:
            return device_entry.area_id

        entity_registry = er.async_get(self.hass)
        matches = {
            entry.area_id
            for entry in entity_registry.entities.values()
            if entry.device_id == device_id and entry.area_id
        }
        if len(matches) == 1:
            return matches.pop()
        return None

    def _area_name(self, area_id: str | None) -> str | None:
        if not area_id:
            return None
        area = ar.async_get(self.hass).async_get_area(area_id)
        if area is None:
            return None
        return area.name

    def _home_assistant_snapshot(self) -> dict[str, Any]:
        area_registry = ar.async_get(self.hass)
        floor_registry = fr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        return {
            "floors": [
                {
                    "floor_id": floor.floor_id,
                    "name": floor.name,
                    "aliases": sorted(floor.aliases or []),
                }
                for floor in floor_registry.async_list_floors()
            ],
            "areas": [
                {
                    "area_id": area.id,
                    "name": area.name,
                    "aliases": sorted(area.aliases or []),
                    "floor_id": area.floor_id,
                }
                for area in area_registry.async_list_areas()
            ],
            "lights": [
                light
                for state in self.hass.states.async_all()
                if state.entity_id.startswith("light.")
                if (light := self._light_snapshot(state, entity_registry, device_registry))
            ],
        }

    def _light_snapshot(
        self,
        state: Any,
        entity_registry: er.EntityRegistry,
        device_registry: dr.DeviceRegistry,
    ) -> dict[str, Any] | None:
        entity_entry = entity_registry.async_get(state.entity_id)
        area_id = None
        if entity_entry:
            area_id = entity_entry.area_id
            if area_id is None and entity_entry.device_id:
                device_entry = device_registry.async_get(entity_entry.device_id)
                if device_entry:
                    area_id = device_entry.area_id

        if area_id is None:
            return None

        return {
            "entity_id": state.entity_id,
            "state": state.state,
            "area_id": area_id,
            "name": state.name,
        }
