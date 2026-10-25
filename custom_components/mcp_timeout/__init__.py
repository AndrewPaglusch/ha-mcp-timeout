"""Give the Model Context Protocol integration's tool calls a usable timeout.

The core `mcp` integration wraps each tool call in a 10 or 30 second
asyncio timeout but builds its httpx client without one, so httpx's 5 second
default read timeout cancels any tool call that takes longer than that. This
integration wraps the client factory the `mcp` coordinator module uses so the
httpx client gets a real timeout, and raises the outer timeout to match.
"""

import functools
import importlib
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "mcp_timeout"
CONF_TIMEOUT = "timeout"
DEFAULT_TIMEOUT = 30
COORDINATOR = "homeassistant.components.mcp.coordinator"
FACTORIES = ("create_mcp_httpx_client", "create_async_httpx_client")

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    timeout = config[DOMAIN][CONF_TIMEOUT]
    try:
        coordinator = await hass.async_add_import_executor_job(
            importlib.import_module, COORDINATOR
        )
    except ImportError as err:
        _LOGGER.error("Could not import %s, nothing patched: %s", COORDINATOR, err)
        return False

    name = next((n for n in FACTORIES if callable(getattr(coordinator, n, None))), None)
    if name is None:
        _LOGGER.error(
            "%s has none of %s; this Home Assistant version needs a new release of %s",
            COORDINATOR,
            FACTORIES,
            DOMAIN,
        )
        return False

    factory = getattr(coordinator, name)
    if getattr(factory, "_mcp_timeout", None) == timeout:
        return True
    original = getattr(factory, "func", factory)
    patched = functools.partial(original, timeout=float(timeout))
    patched._mcp_timeout = timeout
    setattr(coordinator, name, patched)

    outer = getattr(coordinator, "TIMEOUT", None)
    if isinstance(outer, (int, float)) and outer < timeout:
        coordinator.TIMEOUT = timeout

    _LOGGER.info(
        "MCP tool calls now time out after %ss (httpx client via %s.%s, outer timeout %s)",
        timeout,
        COORDINATOR,
        name,
        getattr(coordinator, "TIMEOUT", "n/a"),
    )
    return True
