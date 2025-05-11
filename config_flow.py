"""Config flow for Nightscout Data integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_SENSOR_ALARM,
    CONF_SENSOR_BASAL,
    CONF_SENSOR_COB,
    CONF_SENSOR_GL,
    CONF_SENSOR_IOB,
    CONF_SERVER,
    DEFAULT_SENSOR_ALARM,
    DEFAULT_SENSOR_BASAL,
    DEFAULT_SENSOR_COB,
    DEFAULT_SENSOR_GL,
    DEFAULT_SENSOR_IOB,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVER): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
    }
)

STEP_SENSORS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSOR_GL, default=DEFAULT_SENSOR_GL): cv.boolean,
        vol.Required(CONF_SENSOR_IOB, default=DEFAULT_SENSOR_IOB): cv.boolean,
        vol.Required(CONF_SENSOR_COB, default=DEFAULT_SENSOR_COB): cv.boolean,
        vol.Required(CONF_SENSOR_BASAL, default=DEFAULT_SENSOR_BASAL): cv.boolean,
        vol.Required(CONF_SENSOR_ALARM, default=DEFAULT_SENSOR_ALARM): cv.boolean,
    }
)


class NightscoutConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nightscout Data."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.server_url: str | None = None
        self.api_key: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                server_url = user_input[CONF_SERVER]
                api_key = user_input.get(CONF_API_KEY)
                
                # Clean up the server URL
                if not server_url.startswith(("http://", "https://")):
                    server_url = f"https://{server_url}"

                # Test connection
                await self._test_connection(server_url, api_key)

                # Save data for next step
                self.server_url = server_url
                self.api_key = api_key

                # Check if already configured
                await self.async_set_unique_id(server_url)
                self._abort_if_unique_id_configured()

                # Move to sensors selection step if connection is valid
                return await self.async_step_sensors()

            except aiohttp.ClientResponseError as err:
                _LOGGER.error("Authentication error: %s", err)
                if err.status in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except aiohttp.ClientConnectorError:
                _LOGGER.error("Connection error to %s", server_url)
                errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                _LOGGER.error("Client error connecting to %s", server_url)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the sensors selection step."""
        if user_input is not None:
            data = {
                CONF_SERVER: self.server_url,
                CONF_API_KEY: self.api_key,
                CONF_SENSOR_GL: user_input[CONF_SENSOR_GL],
                CONF_SENSOR_IOB: user_input[CONF_SENSOR_IOB],
                CONF_SENSOR_COB: user_input[CONF_SENSOR_COB],
                CONF_SENSOR_BASAL: user_input[CONF_SENSOR_BASAL],
                CONF_SENSOR_ALARM: user_input[CONF_SENSOR_ALARM],
            }
            return self.async_create_entry(
                title=f"Nightscout: {self.server_url}", data=data
            )

        return self.async_show_form(
            step_id="sensors", data_schema=STEP_SENSORS_DATA_SCHEMA
        )

    async def _test_connection(self, server_url: str, api_key: str | None) -> bool:
        """Test connection to Nightscout server."""
        # Ensure URL ends with slash
        if not server_url.endswith("/"):
            server_url += "/"

        # First try status endpoint which should work even without auth for most installations
        status_url = f"{server_url}api/v1/status"
        if api_key:
            status_url += f"?token={api_key}"

        # Also test entries endpoint which typically requires auth
        entries_url = f"{server_url}api/v1/entries/sgv?count=1"
        if api_key:
            entries_url += f"&token={api_key}"

        session_timeout = aiohttp.ClientTimeout(total=10)
        
        try:
            async with aiohttp.ClientSession(timeout=session_timeout) as session:
                # First check status endpoint
                async with session.get(status_url) as resp:
                    if resp.status not in (200, 304):
                        error_text = await resp.text()
                        _LOGGER.error(
                            "Failed to connect to Nightscout status API. Status: %s, Response: %s",
                            resp.status,
                            error_text[:200]
                        )
                        if resp.status in (401, 403):
                            raise aiohttp.ClientResponseError(
                                request_info=resp.request_info,
                                history=resp.history,
                                status=resp.status,
                                message="Authentication failed. Check your API key.",
                                headers=resp.headers,
                            )
                        raise aiohttp.ClientError(f"Invalid response from status endpoint: {resp.status}")
                
                # Then check entries endpoint which typically requires authentication
                async with session.get(entries_url) as resp:
                    if resp.status in (401, 403):
                        _LOGGER.error(
                            "Authentication failed when accessing entries API. Status: %s", 
                            resp.status
                        )
                        raise aiohttp.ClientResponseError(
                            request_info=resp.request_info,
                            history=resp.history,
                            status=resp.status,
                            message="Authentication failed when accessing entries. Check your API key.",
                            headers=resp.headers,
                        )
                    if resp.status not in (200, 304):
                        error_text = await resp.text()
                        _LOGGER.error(
                            "Failed to connect to Nightscout entries API. Status: %s, Response: %s",
                            resp.status,
                            error_text[:200]
                        )
                        raise aiohttp.ClientError(f"Invalid response from entries endpoint: {resp.status}")
                    
                # If both pass, connection is good
                return True
                
        except aiohttp.ClientConnectorError as error:
            _LOGGER.error("Connection error: %s", str(error))
            raise aiohttp.ClientError(f"Connection failed: {error}")
        except aiohttp.ClientResponseError as error:
            if error.status in (401, 403):
                _LOGGER.error("Authentication error: %s", str(error))
                raise
            _LOGGER.error("Response error: %s", str(error))
            raise aiohttp.ClientError(f"Response error: {error}")
        except Exception as error:
            _LOGGER.exception("Unexpected error testing connection")
            raise aiohttp.ClientError(f"Unexpected error: {error}")