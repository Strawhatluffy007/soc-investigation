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
    assert {c["id"] for c in client.get("/api/customers").json()} == {"contoso", "fabrikam", "northwind", "tailspin"}

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
    monkeypatch.setattr(factory, "build_provider", lambda *a: FakeExternal())
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


def test_external_llm_switches(tmp_path):
    from app.config import load_settings
    from app.llm.factory import LLMGate
    from app.customers.store import CustomerProfile
    import os
    os.environ.update(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="x", LLM_ALLOW_EXTERNAL="true")
    try:
        gate = LLMGate(load_settings(), state_file=tmp_path / "settings.json")
    finally:
        for k in ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "LLM_ALLOW_EXTERNAL"):
            os.environ.pop(k, None)
    assert gate.external_enabled and gate.allowed(None)[0]
    gate.set_external(False)
    ok, reason = gate.allowed(None)
    assert not ok and "switched off" in reason
    assert gate.status()["external_switch"] is False
    gate.set_external(True)
    assert gate.allowed(None)[0]
    import dataclasses; gate.settings = dataclasses.replace(gate.settings, llm_allow_external=False)
    import pytest
    from app.llm.base import LLMError
    with pytest.raises(LLMError):
        gate.set_external(True)


def test_followup_logs_notes_and_ticket(client, tmp_path):
    inv = client.post("/api/customers/contoso/investigations", data={"title": "Sign-in"},
                      files={"file": ("s.json", example("contoso", "failed-signin.json").encode(), "application/json")}).json()
    path = f"/api/customers/contoso/investigations/{inv['id']}"
    client.patch(path, json={"status": "Closed"})

    # more logs: parsed separately, observables merged, investigation reopened
    extra = '{"DeviceName": "ws-0142", "RemoteIP": "203.0.113.77", "FileName": "invoice.exe"}'
    r = client.post(path + "/followups", data={"kind": "log"},
                    files={"file": ("defender evidence.json", extra.encode(), "application/json")})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ticket"] is None
    fu = out["inv"]["followups"][0]
    assert fu["kind"] == "log" and fu["source_name"] == "defender_evidence.json" and fu["id"] == "F1"
    assert out["inv"]["status"] == "Investigating"
    vals = {o["value"]: o for o in out["inv"]["analysis"]["observables"]}
    assert "203.0.113.77" in vals and vals["203.0.113.77"]["sources"][0] == "follow-up F1"
    assert "185.220.101.47" in vals  # original observables kept
    assert out["inv"]["analysis"]["parsed"]["followup_logs"] == 1
    o = fu["output"]
    assert o["reanalyzed"] and o["engine"]["mode"] == "rules" and o["answer"] == ""
    assert {"type": "IP address", "value": "203.0.113.77"} in o["new_observables"] or \
        any(x["value"] == "203.0.113.77" for x in o["new_observables"])
    assert not any(x["value"] == "185.220.101.47" for x in o["new_observables"])  # only what is new

    # a note asking for a ticket generates one, with the follow-up log as evidence
    r = client.post(path + "/followups", data={"kind": "note", "text": "User confirmed travel. Please create a ticket for this.",
                                               "reanalyze": "false"}).json()
    assert r["ticket"] and "203.0.113.77" in r["ticket"]["ticket"] and "User confirmed travel" in r["ticket"]["ticket"]
    assert [h["action"] for h in r["inv"]["history"]].count("follow-up added") == 2
    assert r["inv"]["followups"][1]["output"] == r["inv"]["followups"][1]["output"] | {
        "reanalyzed": False, "ticket": {"generated": True, "missing": r["ticket"]["missing"], "drafted": []}}

    # plain note without ticket intent, no re-analysis
    r = client.post(path + "/followups", data={"kind": "note", "text": "What next?", "reanalyze": "false"}).json()
    assert r["ticket"] is None and len(r["inv"]["followups"]) == 3

    assert client.post(path + "/followups", data={"kind": "note", "text": "  "}).status_code == 400
    assert client.post(path + "/followups", data={"kind": "bogus", "text": "x"}).status_code == 400
    # isolation
    assert client.post(f"/api/customers/fabrikam/investigations/{inv['id']}/followups",
                       data={"kind": "note", "text": "x"}).status_code == 404
    audit = (tmp_path / "data" / "audit.log").read_text()
    assert "investigation.followup" in audit
    assert "203.0.113.77" not in audit and "confirmed travel" not in audit


def test_followup_size_limit(customers_dir, tmp_path):
    c = make_client(customers_dir, tmp_path, max_log_chars=3000)
    inv = c.post("/api/customers/contoso/investigations", data={"raw_log": "a=1 " * 500}).json()
    r = c.post(f"/api/customers/contoso/investigations/{inv['id']}/followups", data={"kind": "log", "text": "b=2 " * 400})
    assert r.status_code == 400 and "exceed" in r.json()["detail"]


def test_followup_note_reaches_llm(customers_dir, tmp_path, monkeypatch):
    from app.llm import factory
    seen = {}

    class Answering(FakeExternal):
        def analyze(self, system, prompt, schema):
            seen["prompt"] = prompt
            return super().analyze(system, prompt, schema) | {"analyst_response": "Likely benign travel."}

    monkeypatch.setattr(factory, "build_provider", lambda *a: Answering())
    c = make_client(customers_dir, tmp_path, llm_provider="fake", llm_allow_external=True)
    inv = c.post("/api/customers/contoso/investigations",
                 data={"raw_log": example("contoso", "failed-signin.json"), "analyze_now": "false"}).json()
    r = c.post(f"/api/customers/contoso/investigations/{inv['id']}/followups",
               data={"kind": "note", "text": "Is this true positive?", "use_llm": "true", "confirm_external": "true"}).json()
    assert r["inv"]["analysis"]["analyst_response"] == "Likely benign travel."
    assert r["inv"]["followups"][0]["output"]["answer"] == "Likely benign travel."
    assert "Is this true positive?" in seen["prompt"] and "analyst_response" in seen["prompt"]


def test_ticket_template_preview(client):
    names = {p["name"] for p in client.get("/api/ticket-placeholders").json()}
    assert {"title", "findings", "evidence", "analyst_notes"} <= names
    inv = client.post("/api/customers/contoso/investigations",
                      data={"raw_log": example("contoso", "failed-signin.json") + "\npassword=Hunter2!!"}).json()
    tpl = "# {{title}} for {{customer}}\n{{evidence}}\n{{nope}}"
    r = client.post("/api/customers/contoso/ticket-template/preview", json={"template": tpl, "investigation_id": inv["id"]})
    d = r.json()
    assert r.status_code == 200 and "Contoso" in d["ticket"] and "Hunter2" not in d["ticket"]
    assert d["unknown"] == ["nope"] and d["used"] == ["title", "customer", "evidence", "nope"]
    assert client.post("/api/customers/contoso/ticket-template/preview", json={"template": tpl}).status_code == 200
    # isolation: can't preview another customer's investigation
    assert client.post("/api/customers/fabrikam/ticket-template/preview",
                       json={"template": tpl, "investigation_id": inv["id"]}).status_code == 404


def test_soc_standard_template(client):
    starters = {t["id"]: t for t in client.get("/api/ticket-templates").json()}
    assert {"incident-ticket", "soc-standard-ticket"} <= set(starters)
    tpl = starters["soc-standard-ticket"]["content"]
    log = ('{"TimeGenerated": "2026-07-01T07:42:19Z", "UserPrincipalName": "a.lee@contoso.com", '
           '"DeviceName": "LT-0042", "AppDisplayName": "Office 365", "IPAddress": "185.220.101.47"}')
    inv = client.post("/api/customers/contoso/investigations", data={"title": "Odd sign-in", "raw_log": log}).json()
    path = f"/api/customers/contoso/investigations/{inv['id']}"
    d = client.post("/api/customers/contoso/ticket-template/preview", json={"template": tpl, "investigation_id": inv["id"]}).json()
    t = d["ticket"]
    assert d["unknown"] == [] and "client_actions" in d["missing"]
    assert "01/07/2026 08:42:19 BST (07:42:19 UTC)" in t  # British summer time
    assert "**Who:** a.lee@contoso.com" in t and "- Device: LT-0042" in t and "- Application: Office 365" in t
    assert "Prepared" in t and "KQL hunting queries" in t  # factual SOC actions, never "ran"
    client.patch(path, json={"client_actions": "Reset the user's password.", "soc_actions": "Revoked sessions.",
                             "risk": "Possible account takeover.", "severity": "High", "findings": "Not travel."})
    d = client.post("/api/customers/contoso/ticket-template/preview", json={"template": tpl, "investigation_id": inv["id"]}).json()
    assert d["missing"] == [] and "Reset the user's password." in d["ticket"] and "Possible account takeover." in d["ticket"]
    assert "Revoked sessions." in d["ticket"] and d["ticket"].startswith("**Subject:** High | ")


def test_llm_ticket_draft(customers_dir, tmp_path, monkeypatch):
    """Facts come from the log; description/outcome/why/client actions from the LLM
    draft (labelled) until the analyst writes their own."""
    from app.llm import factory
    draft = {"description": "a.lee signed in from a Tor exit node.", "outcome": "Suspicious, pending user confirmation.",
             "why": "Possible account takeover.", "client_actions": ["Confirm the sign-in with the user.", "Reset the password."]}

    class Drafting(FakeExternal):
        def analyze(self, system, prompt, schema):
            assert "ticket" in schema["required"]
            return super().analyze(system, prompt, schema) | {"ticket": draft}

    monkeypatch.setattr(factory, "build_provider", lambda *a: Drafting())
    c = make_client(customers_dir, tmp_path, llm_provider="fake", llm_allow_external=True)
    tpl = {t["id"]: t for t in c.get("/api/ticket-templates").json()}["soc-standard-ticket"]["content"]
    log = '{"TimeGenerated": "2026-07-01T07:42:19Z", "UserPrincipalName": "a.lee@contoso.com", "IPAddress": "185.220.101.47"}'
    inv = c.post("/api/customers/contoso/investigations", data={"raw_log": log, "analyze_now": "false"}).json()
    path = f"/api/customers/contoso/investigations/{inv['id']}"
    c.post(path + "/analyze", json={"use_llm": True, "confirm_external": True})
    prev = lambda: c.post("/api/customers/contoso/ticket-template/preview",
                          json={"template": tpl, "investigation_id": inv["id"]}).json()
    d = prev()
    t = d["ticket"]
    assert d["drafted"] == ["client_actions", "description", "findings", "why"] and d["missing"] == ["severity"]
    assert "a.lee signed in from a Tor exit node.\n_(LLM draft" in t and "- Reset the password." in t
    assert "Outcome: Suspicious, pending user confirmation." in t and "**Who:** a.lee@contoso.com" in t
    assert "01/07/2026 08:42:19 BST" in t  # still extracted from the log
    c.patch(path, json={"findings": "Confirmed travel.", "client_actions": "None.", "risk": "Low."})
    d = prev()
    assert d["drafted"] == ["description"] and "Confirmed travel." in d["ticket"] and "Reset the password." not in d["ticket"]
