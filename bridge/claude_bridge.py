#!/usr/bin/env python3
"""Host-side bridge: lets the SOC container use the local Claude Code CLI.

The container can't run the host's logged-in `claude` binary, so this tiny
stdlib HTTP server does it. POST /analyze {system, prompt, schema, model}
→ runs `claude -p` with no tools, no MCP, no settings and no session
persistence, in an empty temp directory, and returns {"result": {...}}.

Note: the CLI runs locally but inference happens at Anthropic. The SOC app
therefore treats this provider as external.

Env:
  CLAUDE_BRIDGE_TOKEN   required shared secret (Bearer)
  CLAUDE_BRIDGE_HOST    bind address (default 127.0.0.1; use the docker
                        network gateway, e.g. 172.30.90.1, for the container)
  CLAUDE_BRIDGE_PORT    default 8765
  CLAUDE_BIN            default: claude on PATH
  CLAUDE_BRIDGE_TIMEOUT seconds per request (default 240)
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ.get("CLAUDE_BRIDGE_TOKEN", "")
HOST = os.environ.get("CLAUDE_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLAUDE_BRIDGE_PORT", "8765"))
CLAUDE = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"
TIMEOUT = int(os.environ.get("CLAUDE_BRIDGE_TIMEOUT", "240"))
# Drop API credentials so the CLI always uses the Claude Pro/Max login (`claude auth login`), never API billing.
SUBSCRIPTION_ENV = {k: v for k, v in os.environ.items()
                    if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_BRIDGE_TOKEN")}
MAX_BODY = 2_000_000
ONE_AT_A_TIME = threading.Semaphore(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("claude-bridge")


def run_claude(system: str, prompt: str, schema: dict, model: str = "") -> dict:
    cmd = [CLAUDE, "-p", "--output-format", "json", "--tools", "", "--setting-sources", "",
           "--strict-mcp-config", "--no-session-persistence", "--system-prompt", system,
           "--json-schema", json.dumps(schema)]
    if model:
        cmd += ["--model", model]
    with tempfile.TemporaryDirectory(prefix="soc-bridge-") as cwd:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=TIMEOUT, cwd=cwd,
                              env=SUBSCRIPTION_ENV)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}")
    out = json.loads(proc.stdout)
    if out.get("is_error"):
        raise RuntimeError(f"claude error: {str(out.get('result'))[:400]}")
    result = out.get("structured_output")
    if not isinstance(result, dict):
        raise RuntimeError("claude returned no structured_output")
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "claude-bridge"

    def log_message(self, fmt, *args):  # no request bodies in logs
        log.info("%s %s", self.address_string(), fmt % args)

    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"ok": True})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        auth = self.headers.get("Authorization", "")
        if not hmac.compare_digest(auth.encode(), f"Bearer {TOKEN}".encode()):
            return self._send(401, {"error": "unauthorized"})
        if self.path != "/analyze":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            return self._send(413, {"error": "body too large or empty"})
        try:
            req = json.loads(self.rfile.read(length))
            system, prompt, schema = req["system"], req["prompt"], req["schema"]
        except (ValueError, KeyError):
            return self._send(400, {"error": "expected JSON {system, prompt, schema}"})
        if not ONE_AT_A_TIME.acquire(timeout=TIMEOUT):
            return self._send(503, {"error": "busy"})
        try:
            log.info("analyze: prompt %d chars, model=%s", len(prompt), req.get("model") or "default")
            return self._send(200, {"result": run_claude(system, prompt, schema, req.get("model") or "")})
        except subprocess.TimeoutExpired:
            return self._send(504, {"error": f"claude timed out after {TIMEOUT}s"})
        except Exception as e:
            log.warning("analyze failed: %s", e)
            return self._send(502, {"error": str(e)[:500]})
        finally:
            ONE_AT_A_TIME.release()


def main() -> None:
    if len(TOKEN) < 16:
        sys.exit("Set CLAUDE_BRIDGE_TOKEN to a random value of at least 16 characters.")
    log.info("claude bridge on %s:%d using %s", HOST, PORT, CLAUDE)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
