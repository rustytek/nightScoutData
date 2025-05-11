"""Config flow for Nightscout integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_URL): str,
    vol.Optional(CONF_API_KEY): str,
})

async def validate_input(data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    url = data[CONF_URL].rstrip('/')
    api_key = data.get(CONF_API_KEY)

    headers = {"Accept": "application/json"}
    if api_key:
        headers["api-secret"] = api_key

    test_url = f"{url}/api/v1/status.json"
    
    session = async_get_clientsession()
    try:
        async with aiohttp.ClientTimeout(total=10):
            async with session.get(test_url, headers=headers) as resp:
                if resp.status == 401:
                    raise ConfigEntryAuthFailed("Invalid API key")
                resp.raise_for_status()
                
                # Verify we got valid JSON
                data = await resp.json(content_type=None)
                if not isinstance(data, dict):
                    raise ValueError("Invalid JSON response format")
    except aiohttp.ClientError as err:
        raise CannotConnect from err
    except ValueError as err:
        raise InvalidData from err

    return {"title": "Nightscout"}

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nightscout."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(user_input)
                user_input[CONF_URL] = user_input[CONF_URL].rstrip('/')
                
                await self.async_set_unique_id(user_input[CONF_URL])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input
                )
                
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidData:
                errors["base"] = "invalid_data"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidData(HomeAssistantError):
    """Error to indicate there is invalid data."""
