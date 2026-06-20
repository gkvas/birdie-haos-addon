#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -euo pipefail

OPTIONS=/data/options.json

VENDOR=$(bashio::config 'vendor')
MODEL=$(bashio::config 'model')
API_KEY=$(bashio::config 'api_key')
HA_URL=$(bashio::config 'ha_url')
HA_TOKEN=$(bashio::config 'ha_token')

if bashio::var.is_empty "${API_KEY}"; then
    bashio::exit.nok "Set 'api_key' for the selected vendor (${VENDOR}) in the add-on configuration."
fi
if bashio::var.is_empty "${HA_TOKEN}"; then
    bashio::exit.nok "Set 'ha_token' (a Home Assistant long-lived access token) in the add-on configuration."
fi

# Persist birdie state (sessions, long-term memory, the rendered skill) in /data,
# which survives restarts and updates.
export HOME=/data
SKILL_DIR="${HOME}/.birdie/skills/home_assistant"
mkdir -p "${SKILL_DIR}"

# Render the Home Assistant MCP skill from the template (token never baked into the image).
sed -e "s|\${HA_URL}|${HA_URL}|g" \
    -e "s|\${HA_TOKEN}|${HA_TOKEN}|g" \
    /skill/SKILL.MD.tmpl > "${SKILL_DIR}/SKILL.MD"

# Auto-enable home_assistant plus any extra skills the user opted into.
SKILLS_JSON=$(jq -c '(["home_assistant"] + (.extra_skills // []))' "${OPTIONS}")
export LLM_PROVIDER_CONFIG
LLM_PROVIDER_CONFIG=$(jq -nc \
    --arg vendor "${VENDOR}" \
    --arg model "${MODEL}" \
    --arg key "${API_KEY}" \
    --argjson skills "${SKILLS_JSON}" \
    '{vendor:$vendor, model:$model, api_key:$key, skills_enabled:$skills}')

bashio::log.info "Starting Birdie (vendor=${VENDOR}, model=${MODEL}, HA=${HA_URL}, skills=${SKILLS_JSON})"

# Optional: conversation-agent HTTP bridge for the birdie_conversation integration.
if bashio::config.true 'enable_conversation_api'; then
    API_SECRET=$(bashio::config 'api_secret')
    if bashio::var.is_empty "${API_SECRET}"; then
        bashio::log.warning "enable_conversation_api is on but 'api_secret' is empty - conversation API disabled."
    else
        export BIRDIE_API_SECRET="${API_SECRET}"
        export BIRDIE_API_PORT=7682
        bashio::log.info "Starting Birdie conversation API on :7682"
        python3 /opt/birdie_api/server.py &
    fi
fi

# Serve the birdie TUI over a web terminal; HA Ingress proxies port 7681.
exec ttyd -W -p 7681 -t 'titleFixed=Birdie' -t 'fontSize=14' birdie
