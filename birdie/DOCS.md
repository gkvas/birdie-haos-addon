# Birdie

Birdie is a LangGraph agent that uses **Mistral** as its brain and the **Home
Assistant MCP Server** as its tools. Talk to it from the terminal in the sidebar.

## Configuration

| Option | Description |
|---|---|
| `mistral_api_key` | Your Mistral API key (required). |
| `ha_token` | A Home Assistant long-lived access token (required). Profile → Security → Long-lived access tokens. |
| `model` | Mistral model. Default `mistral-large-latest`. |
| `ha_url` | Internal URL to HA core. Default `http://homeassistant:8123` — leave as-is. |
| `extra_skills` | Extra Birdie skills to enable, e.g. `["Shell", "DuckDuckGo"]`. Off by default. |

## Before first use

1. Enable the **Model Context Protocol Server** integration in Home Assistant
   (Settings → Devices & Services → Add Integration), exposing the `Assist` API.
2. Expose the entities Birdie may control under Settings → Voice assistants → Expose.

## Usage

Open **Birdie** from the sidebar. The `home_assistant` skill is enabled
automatically — try:

- `what is the temperature in the office?`
- `turn off the kitchen light`
- `/skill list` to see all skills and their status

Sessions and long-term memory persist across restarts (stored in `/data`).
