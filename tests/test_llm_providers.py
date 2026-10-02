import json
import stat

import httpx

from app.llm.ollama import OllamaProvider
from tests.test_api import make_client


def test_provider_list_and_switching(customers_dir, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = make_client(customers_dir, tmp_path, llm_provider="none", llm_allow_external=True)
    r = c.get("/api/llm/providers").json()
    ids = {p["id"]: p for p in r["providers"]}
    assert r["active"] == "none"
    assert ids["claude_pro"]["auth"] == "login" and ids["chatgpt"]["auth"] == "login"
    assert ids["openai"]["auth"] == "api_key" and ids["openai"]["key_source"] == ""

    # OpenAI without a key: selectable, but not available
    st = c.put("/api/llm/active", json={"provider": "openai"}).json()
    assert st["active"] == "openai" and not st["available"] and "No API key" in st["reason"]

    r = c.put("/api/llm/providers/openai/key", json={"api_key": "sk-test-1234567890abcdef"})
    assert r.status_code == 200 and r.json()["key_source"] == "saved"
    st = r.json()["llm"]
    assert st["available"] and st["external"] and st["provider"] == "openai"

    # the key is stored 0600 and never returned by the API or written to the audit log
    keyfile = tmp_path / "data" / "secrets" / "llm-keys.json"
    assert stat.S_IMODE(keyfile.stat().st_mode) == 0o600
    assert json.loads(keyfile.read_text())["openai"].startswith("sk-test")
    assert "sk-test" not in c.get("/api/llm/providers").text
    audit = (tmp_path / "data" / "audit.log").read_text()
    assert "settings.llm_key.set" in audit and "sk-test" not in audit

    assert c.put("/api/llm/providers/openai", json={"model": "gpt-5-mini"}).json()["model"] == "gpt-5-mini"
    assert c.put("/api/llm/providers/openai", json={"model": "bad model;"}).status_code == 400
    assert c.put("/api/llm/providers/openai", json={"base_url": "https://evil.example"}).status_code == 400
    assert c.put("/api/llm/providers/openai/key", json={"api_key": "has spaces in it"}).status_code == 400
    assert c.put("/api/llm/active", json={"provider": "nope"}).status_code == 404

    assert c.delete("/api/llm/providers/openai/key").json()["key_source"] == ""
    assert c.put("/api/llm/active", json={"provider": "none"}).json()["configured"] is False


def test_env_key_wins_and_is_locked(customers_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-123456789")
    c = make_client(customers_dir, tmp_path, llm_allow_external=True)
    gem = [p for p in c.get("/api/llm/providers").json()["providers"] if p["id"] == "gemini"][0]
    assert gem["key_source"] == "env"
    r = c.put("/api/llm/providers/gemini/key", json={"api_key": "other-key-123456"})
    assert r.status_code == 400 and "GEMINI_API_KEY" in r.json()["detail"]


def test_openai_compat_falls_back_to_json_mode(monkeypatch):
    from app.llm.openai_compat import OpenAICompatProvider
    bodies = []

    def fake_post(url, json=None, headers=None, timeout=None):
        bodies.append(json)
        if json["response_format"]["type"] == "json_schema":
            return httpx.Response(400, json={"error": "unsupported"})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop",
                                                      "message": {"content": '```json\n{"a": 1}\n```'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    p = OpenAICompatProvider("openai", "OpenAI API", "https://api.openai.com/v1", "k" * 20, "gpt-5", 10)
    assert p.analyze("sys", "prompt", {"type": "object"}) == {"a": 1}
    assert len(bodies) == 2 and "JSON Schema" in bodies[1]["messages"][0]["content"]


def test_pick_llm_per_run(customers_dir, tmp_path, monkeypatch):
    from app.llm import openai_compat
    from tests.test_api import example
    calls = []

    def fake_analyze(self, system, prompt, schema):
        calls.append(self.name)
        return {"event_summary": "from " + self.name, "event_type": "x", "observed": [], "inferred": [], "unknown": [],
                "hypotheses": [], "kql_queries": [], "recommended_steps": []}

    monkeypatch.setattr(openai_compat.OpenAICompatProvider, "analyze", fake_analyze)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-123456789")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key-123456789")
    c = make_client(customers_dir, tmp_path, llm_provider="openai", llm_allow_external=True)
    choices = {x["id"]: x for x in c.get("/api/customers/contoso").json()["llm"]["choices"]}
    assert choices["openai"]["default"] and choices["openai"]["available"]
    assert choices["gemini"]["available"] and not choices["gemini"]["default"]

    raw = example("contoso", "failed-signin.json")
    form = {"raw_log": raw, "use_llm": "true", "confirm_external": "true"}
    inv = c.post("/api/customers/contoso/investigations", data={**form, "llm_provider": "gemini"}).json()
    assert calls == ["gemini"] and inv["llm_used"][-1]["provider"] == "gemini"
    inv = c.post(f"/api/customers/contoso/investigations/{inv['id']}/analyze",
                 json={"use_llm": True, "confirm_external": True, "llm_provider": "openai"}).json()
    assert calls == ["gemini", "openai"] and inv["llm_used"][-1]["provider"] == "openai"
    # default provider when none is picked; unknown and customer-blocked picks are refused
    c.post("/api/customers/contoso/investigations", data=form)
    assert calls[-1] == "openai"
    r = c.post("/api/customers/contoso/investigations", data={**form, "llm_provider": "bogus"})
    assert r.status_code == 400
    r = c.post("/api/customers/fabrikam/investigations", data={**form, "llm_provider": "gemini"})
    assert r.status_code == 400 and "does not permit" in r.json()["detail"]


def test_ollama_sends_context_window_and_strips_thinking(monkeypatch):
    sent = {}

    def fake_post(url, json, timeout):
        sent.update(json)
        return httpx.Response(200, json={"message": {"content": '<think>hmm</think>\n{"event_summary": "x"}'}},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    out = OllamaProvider("http://h:11434/", "qwen3:8b", True, 30, num_ctx=12288).analyze("sys", "prompt", {})
    assert out == {"event_summary": "x"}
    assert sent["options"]["num_ctx"] == 12288 and sent["think"] is False and sent["model"] == "qwen3:8b"
