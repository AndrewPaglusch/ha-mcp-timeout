# MCP Client Timeout for Home Assistant

Home Assistant's [Model Context Protocol](https://www.home-assistant.io/integrations/mcp) integration gives up on any tool call that takes longer than about 5 seconds. This custom integration raises that to 30 seconds (or whatever you set) without editing Home Assistant's own code.

## The problem

The `mcp` integration wraps each tool call in an `asyncio.timeout` of 10 seconds (30 since Home Assistant 2026.11), but the httpx client it talks to the server with is created without a timeout of its own. httpx then applies its default of 5 seconds between bytes, and a server that takes 6 seconds to answer gets its connection closed before the outer timeout ever matters. The assistant reports "Timeout when calling tool", the server finishes the work anyway, and the assistant often retries, so a slow "add to cart" can land twice.

Any tool that drives a browser, calls a slow API, or fetches a web page runs into this.

## What this does

On startup the integration imports `homeassistant.components.mcp.coordinator`, wraps the function it uses to build its httpx client so every client gets `timeout=<your value>`, and raises the module's outer `TIMEOUT` to the same value if it is lower. Python resolves both names when a tool call happens, so the patch applies from the first call after startup regardless of load order. Nothing on disk changes, and a Home Assistant upgrade leaves it in place.

It knows the two shapes the coordinator has had so far (`create_async_httpx_client` through 2026.10 and `create_mcp_httpx_client` from 2026.11). If a future version has neither, setup fails with an error in the log and the `mcp` integration keeps its stock behaviour.

## Install

With [HACS](https://hacs.xyz): add `https://github.com/AndrewPaglusch/ha-mcp-timeout` as a custom repository of type Integration, then download it.

By hand: copy `custom_components/mcp_timeout` into your `config/custom_components` directory.

Then enable it in `configuration.yaml` and restart Home Assistant:

```yaml
mcp_timeout:
```

To use a different limit:

```yaml
mcp_timeout:
  timeout: 60
```

The value is in seconds and applies to every MCP server you have configured.

On startup the integration logs one line at info level saying what it patched. Home Assistant hides info by default, so to see it add:

```yaml
logger:
  logs:
    custom_components.mcp_timeout: info
```

```
MCP tool calls now time out after 30s (httpx client via homeassistant.components.mcp.coordinator.create_async_httpx_client, outer timeout 30)
```

## Remove

Delete the `mcp_timeout:` entry and the `custom_components/mcp_timeout` directory, then restart. There is nothing else to undo.

## Caveats

This reaches into a core integration's module at runtime. It is a workaround, not a supported extension point, and the right fix is for the `mcp` integration to pass a timeout to its httpx client. When that lands, this integration can be removed.
