# Birdie Home Assistant Add-on

Runs [Birdie](https://github.com/gkvas/birdie) — a LangGraph agent — as a Home
Assistant OS add-on, powered by your choice of LLM provider (**Mistral**,
**Anthropic**, or **OpenAI**) and wired to the **Home Assistant MCP Server** so it
can see and control your home. You interact with it through its terminal UI, served
in the HA sidebar via Ingress.

```
Browser (HA sidebar / Ingress)
   │ ttyd web terminal
   ▼
Birdie add-on ── LLM (vendor/model from config)
   └── home_assistant skill (MCP / SSE) ──► HA core /mcp_server/sse
```

## Install

1. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**,
   add `https://github.com/gkvas/birdie-haos-addon`.
2. Install **Birdie** from the store.
3. Open the add-on **Configuration** tab and set:
   - `vendor` — LLM provider: `mistral` (default), `anthropic`, or `openai`
   - `model` — model name for that vendor (default `mistral-large-latest`;
     e.g. `claude-sonnet-4-6` for anthropic, `gpt-4o` for openai)
   - `api_key` — API key for the selected vendor
   - `ha_token` — a Home Assistant **long-lived access token**
     (Profile → Security → Long-lived access tokens → Create token)
   - `ha_url` — defaults to `http://homeassistant:8123` (internal; leave as-is)
   - `extra_skills` — optional, e.g. `Shell`, `DuckDuckGo` (off by default; see
     the security note below)
4. **Start** the add-on, then open **Birdie** from the sidebar.

## Home Assistant prerequisites (one-time)

The add-on talks to HA over the MCP Server integration, which must be enabled and
have entities exposed to Assist:

1. **Settings → Devices & Services → Add Integration → "Model Context Protocol
   Server"** → confirm (expose the `Assist` API).
2. **Settings → Voice assistants → Expose** — expose the entities Birdie should be
   allowed to see and control. Birdie can only act on exposed entities.

## How it works

- `run.sh` reads the add-on options, renders the `home_assistant` MCP skill from
  `rootfs/skill/SKILL.MD.tmpl` into `~/.birdie/skills/`, and sets
  `LLM_PROVIDER_CONFIG` (vendor/model/api_key) so Birdie starts with the chosen
  provider and the HA skill enabled.
- The skill declares an `mcp_server` block (`transport: sse`,
  `url: <ha_url>/mcp_server/sse`, Bearer `ha_token`); Birdie discovers the HA tools
  (`HassTurnOn`, `HassClimateSetTemperature`, `GetLiveContext`, …) at runtime.
- State (`~/.birdie/sessions`, long-term memory) is stored under `/data`, so it
  survives restarts and updates.

## Security

Birdie's `Shell` and `Filesystem` skills can run/read/write anything in the
container. Only `home_assistant` is enabled by default. Add others via
`extra_skills` only if you understand the implications. The `ha_token` grants
Birdie the permissions of the user who created it — scope what you expose to Assist
accordingly.
