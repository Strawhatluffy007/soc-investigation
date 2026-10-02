import pytest

from app.customers.schema import parse_tables
from app.security import InputError


def test_tables_from_customer_md_and_schema_files(contoso):
    assert {"SigninLogs", "AuditLogs", "DeviceProcessEvents", "EmailEvents"} <= set(contoso.tables)
    assert contoso.tables["DeviceProcessEvents"].source == "schemas/defender-xdr.md"
    assert contoso.tables["SigninLogs"].role("time") == "TimeGenerated"
    assert contoso.tables["SigninLogs"].role("user") == "UserPrincipalName"


def test_customers_have_different_conventions(fabrikam):
    t = fabrikam.tables["AADSignInEventsBeta"]
    assert t.role("time") == "Timestamp" and t.role("user") == "AccountUpn"
    assert "SigninLogs" not in fabrikam.tables
    assert fabrikam.allow_external_llm is False
    assert fabrikam.ticket_template_source == "customer"


def test_role_hint_overrides_candidates():
    md = "### T\nTime field: When\n- When\n- Who (user)\n- UserPrincipalName\n"
    t = parse_tables(md, "x")[0]
    assert t.role("user") == "Who" and t.role("time") == "When"


def test_markdown_table_rows_are_parsed():
    md = "### Foo\n| Field | Type |\n|---|---|\n| TimeGenerated | datetime |\n| Account | string |\n"
    assert parse_tables(md, "x")[0].fields == ["TimeGenerated", "Account"]


def test_path_traversal_rejected(store):
    for bad in ("../etc", "Contoso", "a/b", "_template", ""):
        with pytest.raises((InputError, KeyError)):
            store.load(bad)
    with pytest.raises(InputError):
        store.write_file("contoso", "schema", "x", "../../evil.md")


def test_create_customer_from_template(store):
    p = store.create("Northwind Traders")
    assert p.id == "northwind-traders" and p.name == "Northwind Traders"
    assert "SigninLogs" in p.tables
    with pytest.raises(InputError):
        store.create("Northwind Traders")
    assert "_template" not in [c["id"] for c in store.list()]
