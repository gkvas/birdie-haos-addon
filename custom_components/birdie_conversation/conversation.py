"""Conversation platform that forwards Home Assistant Assist to Birdie."""

from __future__ import annotations

import logging

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_API_SECRET,
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register the Birdie conversation entity for this config entry."""
    async_add_entities([BirdieConversationEntity(entry)])


class BirdieConversationEntity(conversation.ConversationEntity):
    """A conversation agent that delegates every turn to the Birdie add-on."""

    _attr_has_entity_name = True
    _attr_name = "Birdie"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        self._url = f"http://{host}:{port}/converse"
        self._secret = entry.data[CONF_API_SECRET]

    @property
    def supported_languages(self) -> list[str] | str:
        # Birdie/the LLM handle any language; let HA pass everything through.
        return "*"

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: "conversation.ChatLog",
    ) -> conversation.ConversationResult:
        """Forward the utterance to Birdie and speak back its reply.

        Birdie owns the tools (HA MCP), system prompt, and per-conversation memory,
        so this method is a thin transport: post text + conversation_id, return the
        reply. The conversation_id round-trips so multi-turn dialogues map to the same
        Birdie session thread.
        """
        cid = user_input.conversation_id or getattr(chat_log, "conversation_id", None)
        session = async_get_clientsession(self.hass)
        response = intent.IntentResponse(language=user_input.language)

        try:
            async with session.post(
                self._url,
                json={"text": user_input.text, "conversation_id": cid},
                headers={"X-Birdie-Token": self._secret},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise RuntimeError(data.get("error", f"HTTP {resp.status}"))
        except Exception as err:  # noqa: BLE001 - report any failure to the user
            _LOGGER.error("Birdie request failed: %s", err)
            response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Birdie is unavailable: {err}",
            )
            return conversation.ConversationResult(
                response=response, conversation_id=cid
            )

        response.async_set_speech(data.get("reply", ""))
        # Return HA's own conversation_id (the one we sent) so HA session tracking
        # stays consistent; Birdie threads its memory on the same id.
        return conversation.ConversationResult(response=response, conversation_id=cid)
