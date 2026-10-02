import base64
import dataclasses
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.llm.base import LLMProvider
from tests.conftest import example


def make_client(customers_dir, tmp_path, **overrides):
    from app.main import create_app
    s = dataclasses.replace(load_settings(), customers_dir=customers_dir, data_dir=tmp_path / "data", **overrides)
    return TestClient(create_app(s))


@pytest.fixture
def client(customers_dir, tmp_path):
    return make_client(customers_dir, tmp_path)


def test_end_to_end(client, tmp_path):
    assert client.get("/healthz").json() == {"ok": True}
    r = client.get("/")
    assert r.status_code == 200 and "Content-Security-Policy" in r.headers
    assert {c["id"] for c in client.get("/api/customers").json()} == {"contoso", "fabrikam"}

    r = client.post("/api/customers/contoso/investigations",
                    data={"title": "Failed admin sign-in", "context": "user reported nothing"},
                    files={"file": ("signin.json", example("contoso", "failed-signin.json").encode(), "application/json")})
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["analysis"]["engine"]["mode"] == "rules"
    assert inv["status"] == "Investigating" and inv["source_name"] == "signin.json"
    path = f"/api/customers/contoso/investigations/{inv['id']}"

    # isolation through the API
    assert client.get(f"/api/customers/fabrikam/investigations/{inv['id']}").status_code == 404

    r = client.patch(path, json={"findings": "Confirmed 1 failure only.", "severity": "Medium", "status": "Escalated"})
    assert r.status_code == 200 and r.json()["severity"] == "Medium"
    assert client.patch(path, json={"status": "Nope"}).status_code == 400

    t = client.post(path + "/ticket").json()
    assert "Confirmed 1 failure only." in t["ticket"] and "[Contoso]" in t["ticket"]

    v = client.post("/api/customers/contoso/kql/validate", json={"query": "Nope | take 1"}).json()
    assert v["status"] == "error"

    audit = (tmp_path / "data" / "audit.log").read_text()
    assert "investigation.create" in audit and "ticket.generate" in audit
    assert "185.220.101.47" not in audit  # raw log content never in audit


def test_upload_limits(customers_dir, tmp_path):
    c = make_client(customers_dir, tmp_path, max_upload_bytes=100)
    r = c.post("/api/customers/contoso/investigations", files={"file": ("x.log", b"a" * 500, "text/plain")})
    assert r.status_code == 400
    r = c.post("/api/customers/contoso/investigations", files={"file": ("x.bin", b"\x00\x01" * 40, "application/octet-stream")})
    assert r.status_code == 400
    assert c.post("/api/customers/contoso/investigations", data={"raw_log": "  "}).status_code == 400


def test_llm_disabled_by_default(client):
    r = client.post("/api/customers/contoso/investigations", data={"raw_log": "x=1", "use_llm": "true"})
    assert r.status_code == 400 and "LLM" in r.json()["detail"]


class FakeExternal(LLMProvider):
    name, is_external, model = "fake", True, "fake-1"
    calls = 0

    def analyze(self, system, prompt, schema):
        FakeExternal.calls += 1
        assert "<untrusted_log>" in prompt and "Hunter2" not in prompt
        return {"event_summary": "LLM summary", "event_type": "sign-in", "observed": ["o"], "inferred": ["i"],
                "unknown": ["u"], "hypotheses": [{"title": "h", "rationale": "r"}],
                "kql_queries": [{"title": "t", "purpose": "p", "table": "SigninLogs", "rationale": "r", "expected_result": "e",
                                 "query": "SigninLogs | where TimeGenerated > ago(1d) | where Bogus == 1"}],
                "recommended_steps": ["s"]}


def test_external_llm_gates(customers_dir, tmp_path, monkeypatch):
    from app.llm import factory
    monkeypatch.setattr(factory, "build_provider", lambda s: FakeExternal())
    c = make_client(customers_dir, tmp_path, llm_provider="fake", llm_allow_external=True)
    raw = example("contoso", "failed-signin.json").replace('"Location"', '"password": "Hunter2!!", "Location"')
    # needs explicit confirmation
    r = c.post("/api/customers/contoso/investigations", data={"raw_log": raw, "use_llm": "true"})
    assert r.status_code == 400 and "confirmation" in r.json()["detail"]
    r = c.post("/api/customers/contoso/investigations", data={"raw_log": raw, "use_llm": "true", "confirm_external": "true"})
    inv = r.json()
    assert inv["analysis"]["engine"]["mode"] == "rules+llm" and inv["llm_used"][0]["external"] is True
    llm_q = [q for q in inv["analysis"]["kql_queries"] if q["source"] == "llm"][0]
    assert llm_q["validation"]["status"] == "warning"  # Bogus column flagged
    # Fabrikam forbids external LLM
    r = c.post("/api/customers/fabrikam/investigations", data={"raw_log": raw, "use_llm": "true", "confirm_external": "true"})
    assert r.status_code == 400 and "does not permit" in r.json()["detail"]
    assert FakeExternal.calls == 1


def test_auth_required_when_exposed(customers_dir, tmp_path):
    with pytest.raises(RuntimeError):
        make_client(customers_dir, tmp_path, bind_addr="0.0.0.0")
    c = make_client(customers_dir, tmp_path, bind_addr="0.0.0.0", auth_password="s3cret")
    assert c.get("/api/customers").status_code == 401
    assert c.get("/healthz").status_code == 200
    tok = base64.b64encode(b"analyst:s3cret").decode()
    r = c.get("/api/status", headers={"Authorization": "Basic " + tok})
    assert r.status_code == 200 and r.json()["analyst"] == "analyst"


def test_rename_customer_and_manage_files(client, customers_dir):
    base = "/api/customers/contoso"
    inv = client.post(base + "/investigations", data={"raw_log": "user=alice", "analyze_now": "false"}).json()

    r = client.patch(base, json={"name": "Contoso Ltd (EU)"})
    assert r.status_code == 200 and r.json()["name"] == "Contoso Ltd (EU)"
    assert (customers_dir / "contoso" / "customer.md").read_text().splitlines()[0] == "# Customer: Contoso Ltd (EU)"
    assert client.get(f"{base}/investigations/{inv['id']}").status_code == 200  # id unchanged, still linked
    assert client.patch(base, json={"name": "  "}).status_code == 400

    # example files: create, list, read, delete
    assert client.put(base + "/files/example", json={"content": "a,b\n1,2\n", "filename": "sample.csv"}).status_code == 200
    assert "sample.csv" in client.get(base).json()["example_files"]
    assert client.get(base + "/files/example?filename=sample.csv").json()["content"] == "a,b\n1,2\n"
    assert client.put(base + "/files/example", json={"content": "x", "filename": "evil.exe"}).status_code == 400
    assert client.put(base + "/files/example", json={"content": "x", "filename": "../x.json"}).status_code == 400
    assert client.delete(base + "/files/example?filename=sample.csv").status_code == 200
    assert "sample.csv" not in client.get(base).json()["example_files"]

    # schema delete; customer.md cannot be deleted; template delete reverts to default
    assert client.delete(base + "/files/schema?filename=defender-xdr.md").status_code == 200
    assert "defender-xdr.md" not in client.get(base).json()["schema_files"]
    assert client.delete(base + "/files/customer").status_code == 400
    assert client.delete(base + "/files/template").status_code == 200
    assert client.get(base + "/files/template").json()["source"] == "default"
    assert client.delete(base + "/files/schema?filename=missing.md").status_code == 404
