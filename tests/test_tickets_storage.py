import pytest

from app.investigation.engine import analyze
from app.security import InputError, scrub_secrets
from app.storage.investigations import InvestigationStore
from app.tickets.render import UNKNOWN, render_ticket
from tests.conftest import example


def _inv(store, profile, raw):
    inv = store.create(profile.id, title="Test", raw_log=raw, context="", analyst="tester")
    return store.save_analysis(profile.id, inv["id"], analyze(profile, raw), "tester")


def test_ids_sequential_and_scoped(tmp_path, contoso, fabrikam):
    s = InvestigationStore(tmp_path)
    a = s.create("contoso", title="a", raw_log="x", context="", analyst="t")
    b = s.create("fabrikam", title="b", raw_log="y", context="", analyst="t")
    assert a["id"].startswith("INV-") and int(b["id"][-6:]) == int(a["id"][-6:]) + 1
    with pytest.raises(KeyError):
        s.get("fabrikam", a["id"])  # isolation: not reachable via another customer
    assert [i["id"] for i in s.list("contoso")] == [a["id"]]
    with pytest.raises(InputError):
        s.get("contoso", "../../counter")


def test_status_validation(tmp_path):
    s = InvestigationStore(tmp_path)
    a = s.create("contoso", title="a", raw_log="x", context="", analyst="t")
    assert s.update("contoso", a["id"], {"status": "Escalated"}, "t")["status"] == "Escalated"
    with pytest.raises(InputError):
        s.update("contoso", a["id"], {"status": "Bogus"}, "t")
    assert s.update("contoso", a["id"], {"customer_id": "fabrikam"}, "t")["customer_id"] == "contoso"


def test_ticket_fills_template_without_inventing(tmp_path, fabrikam):
    s = InvestigationStore(tmp_path)
    inv = _inv(s, fabrikam, example("fabrikam", "phishing-email.csv"))
    text, missing = render_ticket(fabrikam.ticket_template, inv, fabrikam, "tester")
    assert "FABRIKAM SECURITY INCIDENT" in text
    assert "{{" not in text
    assert "[Analyst input required: severity]" in text
    assert "[Analyst input required: findings]" in text
    assert "[Analyst input required: alert_id]" in text  # unknown placeholder → analyst input
    assert UNKNOWN in text  # empty analyst notes
    assert "payroll@fabrikam-hr-portal.com" in text
    assert {"severity", "findings", "alert_id"} <= set(missing)


def test_ticket_redacts_secrets(tmp_path, contoso):
    s = InvestigationStore(tmp_path)
    raw = '{"TimeGenerated":"2026-09-30T01:00:00Z","UserPrincipalName":"a@contoso.com","password":"Hunter2!!","x":"Bearer abcdefghijklmnopqrstuvwxyz123456"}'
    inv = _inv(s, contoso, raw)
    s.update("contoso", inv["id"], {"findings": "api_key=sk-ant-abcdef1234567890"}, "t")
    inv = s.get("contoso", inv["id"])
    text, _ = render_ticket(contoso.ticket_template, inv, contoso)
    assert "Hunter2" not in text and "abcdefghijklmnop" not in text and "sk-ant-abcdef" not in text
    assert "[REDACTED]" in text


def test_scrub_patterns():
    s = scrub_secrets('client_secret="abc12345" token: xyz98765 eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefg AKIAABCDEFGHIJKLMNOP')
    assert "abc12345" not in s and "xyz98765" not in s and "eyJhbGci" not in s and "AKIA" not in s
