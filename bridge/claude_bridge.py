#!/usr/bin/env python3
"""Host-side bridge: lets the SOC container use subscription logins on the host.

The container can't run the host's logged-in CLIs, so this tiny stdlib HTTP
server does it:

  POST /analyze {system, prompt, schema, model, cli}
       cli="claude" → `claude -p` (Claude Pro/Max login), no tools, no MCP,
                      no settings, no session persistence
       cli="codex"  → `codex exec` (ChatGPT Plus/Pro login), read-only sandbox
       Both run in an empty temp directory; returns {"result": {...}}.
  GET  /status          → install + login state of both CLIs
  POST /login {cli}     → codex only: starts `codex login --device-auth` and
                          returns the verification URL and one-time code
  GET  /login/codex     → state of that sign-in

Note: the CLIs run locally but inference happens at Anthropic / OpenAI. The
SOC app therefore treats these providers as external.

Env:
  CLAUDE_BRIDGE_TOKEN   required shared secret (Bearer)
  CLAUDE_BRIDGE_HOST    bind address (default 127.0.0.1; use the docker
                        network gateway, e.g. 172.30.90.1, for the container)
  CLAUDE_BRIDGE_PORT    default 8765
  CLAUDE_BIN            default: claude on PATH
  CODEX_BIN             default: codex on PATH
  CLAUDE_BRIDGE_TIMEOUT seconds per request (default 240)
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import re
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
CODEX = os.environ.get("CODEX_BIN") or shutil.which("codex") or "codex"
TIMEOUT = int(os.environ.get("CLAUDE_BRIDGE_TIMEOUT", "240"))
# Drop API credentials so the CLI always uses the Claude Pro/Max login (`claude auth login`), never API billing.
SUBSCRIPTION_ENV = {k: v for k, v in os.environ.items()
                    if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_BRIDGE_TOKEN",
                                 "OPENAI_API_KEY", "CODEX_API_KEY")}
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


def run_codex(system: str, prompt: str, schema: dict, model: str = "") -> dict:
    with tempfile.TemporaryDirectory(prefix="soc-bridge-") as cwd:
        schema_file, out_file = os.path.join(cwd, ".schema.json"), os.path.join(cwd, ".out.json")
        with open(schema_file, "w") as f:
            json.dump(schema, f)
        cmd = [CODEX, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never",
               "-C", cwd, "--output-schema", schema_file, "--output-last-message", out_file]
        if model:
            cmd += ["-m", model]
        cmd.append("-")  # prompt on stdin
        proc = subprocess.run(cmd, input=f"{system}\n\n{prompt}", capture_output=True, text=True,
                              timeout=TIMEOUT, cwd=cwd, env=SUBSCRIPTION_ENV)
        if proc.returncode != 0:
            raise RuntimeError(f"codex exited {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}")
        try:
            with open(out_file) as f:
                text = f.read().strip()
        except OSError:
            raise RuntimeError("codex wrote no final message")
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    result = json.loads(m.group(1) if m else text)
    if not isinstance(result, dict):
        raise RuntimeError("codex returned no JSON object")
    return result


RUNNERS = {"claude": run_claude, "codex": run_codex}


def _quick(cmd: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=SUBSCRIPTION_ENV,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None


def cli_status() -> dict:
    out = {}
    p = _quick([CLAUDE, "auth", "status"])
    try:
        logged = bool(p and p.returncode == 0 and json.loads(p.stdout).get("loggedIn"))
    except ValueError:
        logged = False
    out["claude"] = {"installed": p is not None, "logged_in": logged}
    p = _quick([CODEX, "login", "status"])
    text = ((p.stdout or "") + (p.stderr or "")) if p else ""
    out["codex"] = {"installed": p is not None,
                    "logged_in": bool(p and p.returncode == 0 and "not logged in" not in text.lower()),
                    "method": "ChatGPT" if "chatgpt" in text.lower() else ("API key" if "api key" in text.lower() else "")}
    return out


class DeviceLogin:
    """One `codex login --device-auth` at a time; the analyst finishes it in a browser."""
    URL_RE = re.compile(r"https://\S+")
    CODE_RE = re.compile(r"\b[A-Z0-9]{4,5}-[A-Z0-9]{4,6}\b")

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.text = ""
        self.lock = threading.Lock()

    def _pump(self, proc: subprocess.Popen) -> None:
        for line in proc.stdout:  # type: ignore[union-attr]
            with self.lock:
                self.text += re.sub(r"\x1b\[[0-9;]*m", "", line)[:400]
        proc.wait()

    def start(self) -> dict:
        with self.lock:
            if self.proc and self.proc.poll() is None:
                return self.state()
            self.text = ""
            self.proc = subprocess.Popen([CODEX, "login", "--device-auth"], stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
                                         env=SUBSCRIPTION_ENV)
        threading.Thread(target=self._pump, args=(self.proc,), daemon=True).start()
        for _ in range(40):  # wait up to ~10s for the URL and code
            with self.lock:
                if self.CODE_RE.search(self.text) or (self.proc.poll() is not None):
                    break
            threading.Event().wait(0.25)
        with self.lock:
            return self.state()

    def state(self) -> dict:
        running = bool(self.proc and self.proc.poll() is None)
        url = self.URL_RE.search(self.text)
        code = self.CODE_RE.search(self.text)
        return {"running": running, "exit_code": None if running or not self.proc else self.proc.returncode,
                "url": url.group(0).rstrip(".,)") if url else "", "code": code.group(0) if code else "",
                "output": self.text[-600:] if not running else ""}


DEVICE_LOGIN = DeviceLogin()


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

    def _authorized(self) -> bool:
        auth = self.headers.get("Authorization", "")
        return hmac.compare_digest(auth.encode(), f"Bearer {TOKEN}".encode())

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"ok": True})
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        if self.path == "/status":
            return self._send(200, cli_status())
        if self.path == "/login/codex":
            with DEVICE_LOGIN.lock:
                return self._send(200, DEVICE_LOGIN.state())
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        if self.path == "/login":
            return self._send(200, DEVICE_LOGIN.start())
        if self.path != "/analyze":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            return self._send(413, {"error": "body too large or empty"})
        try:
            req = json.loads(self.rfile.read(length))
            system, prompt, schema = req["system"], req["prompt"], req["schema"]
            runner = RUNNERS[req.get("cli") or "claude"]
        except (ValueError, KeyError):
            return self._send(400, {"error": "expected JSON {system, prompt, schema, cli: claude|codex}"})
        if not ONE_AT_A_TIME.acquire(timeout=TIMEOUT):
            return self._send(503, {"error": "busy"})
        try:
            log.info("analyze: cli=%s prompt %d chars, model=%s", req.get("cli") or "claude", len(prompt),
                     req.get("model") or "default")
            return self._send(200, {"result": runner(system, prompt, schema, req.get("model") or "")})
        except subprocess.TimeoutExpired:
            return self._send(504, {"error": f"CLI timed out after {TIMEOUT}s"})
        except Exception as e:
            log.warning("analyze failed: %s", e)
            return self._send(502, {"error": str(e)[:500]})
        finally:
            ONE_AT_A_TIME.release()


def main() -> None:
    if len(TOKEN) < 16:
        sys.exit("Set CLAUDE_BRIDGE_TOKEN to a random value of at least 16 characters.")
    log.info("LLM bridge on %s:%d using %s and %s", HOST, PORT, CLAUDE, CODEX)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
