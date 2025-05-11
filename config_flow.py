"""Config flow for Nightscout integration."""

import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError
from py_nightscout import Api as NightscoutAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .utils import hash_from_url

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_URL): str, vol.Optional(CONF_API_KEY): str})


async def _validate_input(data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    url: str = data[CONF_URL]
    api_key: str | None = data.get(CONF_API_KEY)
    try:
        api = NightscoutAPI(url, api_secret=api_key)
        status = await api.get_server_status()
        if status.settings.get("authDefaultRoles") == "status-only":
            await api.get_sgvs()
    except ClientResponseError as error:
        raise InputValidationError("invalid_auth") from error
    except (ClientError, TimeoutError, OSError) as error:
        raise InputValidationError("cannot_connect") from error

    # Return info to be stored in the config entry.
    return {"title": status.name}


class NightscoutConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nightscout."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = hash_from_url(user_input[CONF_URL])
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            try:
                info = await _validate_input(user_input)
            except InputValidationError as error:
                errors["base"] = error.base
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InputValidationError(HomeAssistantError):
    """Error to indicate we cannot proceed due to invalid input."""

    def __init__(self, base: str) -> None:
        """Initialize with error base."""
        super().__init__()
        self.base = base

# Add to the options flow if you want users to toggle these sensors
@staticmethod
def async_get_options_flow(config_entry):
    return NightscoutOptionsFlowHandler(config_entry)

class NightscoutOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SHOW_SENSOR_AGE,
                    default=self.config_entry.options.get(CONF_SHOW_SENSOR_AGE, True)
                ): bool,
                vol.Optional(
                    CONF_SHOW_CANNULA_AGE,
                    default=self.config_entry.options.get(CONF_SHOW_CANNULA_AGE, True)
                ): bool,
            })
        )