"""
Minimal HTTP bridge that exposes Birdie as a Home Assistant conversation agent.

A single long-lived ``DynamicAgent`` is built once at startup (same construction as
``birdie/cli.py:_async_main``) and reused across requests. Each HA conversation maps
to a Birdie ``thread_id`` so multi-turn dialogues get durable, isolated memory via the
``AsyncSqliteSaver`` checkpointer.

Endpoints
---------
GET  /health    -> {"ok": true}                       (no auth; for config-flow probe)
POST /converse  -> {"reply": str, "conversation_id": str}
                   body: {"text": str, "conversation_id": str|null}
                   header: X-Birdie-Token: <BIRDIE_API_SECRET>

Configuration (environment, exported by run.sh)
-----------------------------------------------
LLM_PROVIDER_CONFIG   full JSON provider config (vendor/model/api_key/skills_enabled)
BIRDIE_API_SECRET     shared secret required on /converse
BIRDIE_API_PORT       listen port (default 7682)
BIRDIE_USER           session/user id (default "assist")
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

from aiohttp import web

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from birdie.agent.run import DynamicAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("birdie_api")

SECRET = os.environ.get("BIRDIE_API_SECRET", "")
PORT = int(os.environ.get("BIRDIE_API_PORT", "7682"))
USER = os.environ.get("BIRDIE_USER", "assist")
# Longest a single Assist turn may take before we return a clean error.
TURN_TIMEOUT_S = float(os.environ.get("BIRDIE_API_TIMEOUT", "120"))


def _message_text(message) -> str:
    """Flatten the last LangChain message content to plain text.

    Mirrors the handling in ``birdie/core/acp_mcp_server.py`` where content may be a
    plain string or a list of content blocks.
    """
    content = getattr(message, "content", message)
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        ).strip()
    return str(content).strip()


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def handle_converse(request: web.Request) -> web.Response:
    if not SECRET or request.headers.get("X-Birdie-Token") != SECRET:
        return web.json_response({"error": "unauthorized"}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    text = (body.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "missing 'text'"}, status=400)

    # HA supplies a conversation_id for multi-turn; reuse it as the Birdie thread_id.
    conversation_id = body.get("conversation_id") or uuid.uuid4().hex
    agent: DynamicAgent = request.app["agent"]

    try:
        import asyncio

        state = await asyncio.wait_for(
            agent.invoke(text, thread_id=conversation_id, user_id=USER),
            timeout=TURN_TIMEOUT_S,
        )
        reply = _message_text(state["messages"][-1])
    except asyncio.TimeoutError:
        log.warning("converse timed out after %ss (conversation %s)", TURN_TIMEOUT_S, conversation_id)
        return web.json_response(
            {"error": "timeout", "conversation_id": conversation_id}, status=504
        )
    except Exception as exc:  # surface a clean error to Assist
        log.exception("converse failed")
        return web.json_response(
            {"error": str(exc), "conversation_id": conversation_id}, status=500
        )

    return web.json_response({"reply": reply, "conversation_id": conversation_id})


async def _build_agent(app: web.Application) -> None:
    provider_config = os.environ.get("LLM_PROVIDER_CONFIG")
    if not provider_config:
        raise RuntimeError("LLM_PROVIDER_CONFIG is not set")

    # Bundled skills dir + user skills (~/.birdie/skills) are auto-discovered by
    # DynamicAgent; pass the bundled path explicitly like the CLI does.
    import birdie
    skills_dir = str(Path(birdie.__file__).parent / "skills")

    db_path = Path.home() / ".birdie" / "sessions" / USER / "checkpoints.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Hold the checkpointer open for the server's lifetime (CLI uses the same pattern).
    cm = AsyncSqliteSaver.from_conn_string(str(db_path))
    checkpointer = await cm.__aenter__()
    app["_checkpointer_cm"] = cm

    agent = DynamicAgent.from_config(
        provider_config,
        skills_dir=skills_dir,
        checkpointer=checkpointer,
    )
    app["agent"] = agent
    cfg = json.loads(provider_config)
    log.info(
        "Birdie conversation API ready (vendor=%s model=%s skills=%s) on :%d",
        cfg.get("vendor"), cfg.get("model"), cfg.get("skills_enabled"), PORT,
    )


async def _cleanup_agent(app: web.Application) -> None:
    cm = app.get("_checkpointer_cm")
    if cm is not None:
        await cm.__aexit__(None, None, None)


def main() -> None:
    if not SECRET:
        log.warning("BIRDIE_API_SECRET is empty - /converse will reject all requests")
    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_post("/converse", handle_converse)
    app.on_startup.append(_build_agent)
    app.on_cleanup.append(_cleanup_agent)
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
