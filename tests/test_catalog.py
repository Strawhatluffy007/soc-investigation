import dataclasses

import pytest
from fastapi.testclient import TestClient

from app.catalog.fetch import Fetcher, Source, _check_url, refresh_catalog
from app.catalog.model import parse_catalog, render_catalog, render_table
from app.catalog.store import CatalogStore
from app.config import load_settings
from app.kql.validator import validate_kql

CATALOG = """# Schema catalog

Generated from Microsoft Learn on 2026-10-02T00:00+00:00.

## Schema: Microsoft Sentinel (Log Analytics)
Id: sentinel
Origin: microsoft
Source: https://learn.microsoft.com/x
Time field: TimeGenerated

### SigninLogs
Time field: TimeGenerated
Description: Entra sign-ins
Source: https://learn.microsoft.com/signinlogs

| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | time |
| UserPrincipalName | string | upn |
| IPAddress | string | ip |
| Name | string | a real column called Name |

### SecurityEvent
Time field: TimeGenerated

| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | |
| Computer | string | |
| EventID | int | |

## Schema: Microsoft Defender XDR (Advanced Hunting)
Id: defender-xdr
Origin: microsoft
Time field: Timestamp

### DeviceProcessEvents
Time field: Timestamp

| Column | Type | Description |
|---|---|---|
| Timestamp | datetime | |
| DeviceName | string | |
| ProcessCommandLine | string | |

## Schema: Custom
Id: custom
Origin: custom
Time field: TimeGenerated

### MyApp_CL
| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | |
| UserName_s | string | |
"""


@pytest.fixture
def cat_path(tmp_path):
    p = tmp_path / "catalog" / "schema-catalog.md"
    p.parent.mkdir()
    p.write_text(CATALOG)
    return p


def test_parse_and_roundtrip(cat_path):
    cat = parse_catalog(CATALOG)
    assert list(cat.schemas) == ["sentinel", "defender-xdr", "custom"]
    signin = cat.schemas["sentinel"].tables["SigninLogs"]
    assert [c.name for c in signin.columns] == ["TimeGenerated", "UserPrincipalName", "IPAddress", "Name"]
    assert signin.description == "Entra sign-ins" and signin.time_field == "TimeGenerated"
    again = render_catalog(cat)
    assert render_catalog(parse_catalog(again)) == again


def test_apply_selection_scopes_customer(store, cat_path, customers_dir):
    cs = CatalogStore(cat_path)
    before = store.load("contoso")
    assert "SecurityEvent" in before.tables or "SigninLogs" in before.tables

    res = cs.apply(store, "contoso", {"sentinel": ["SigninLogs"], "custom": ["MyApp_CL"]}, "selected")
    assert res["written"] == ["catalog-custom.md", "catalog-sentinel.md"]
    prof = store.load("contoso")
    assert prof.schema_scope == "selected"
    assert set(prof.tables) == {"SigninLogs", "MyApp_CL"}
    assert "Name" in prof.tables["SigninLogs"].fields  # real column, not mistaken for a header
    assert prof.ignored_tables and "SigninLogs" not in prof.ignored_tables
    assert "- schema_scope: selected" in (customers_dir / "contoso" / "customer.md").read_text()

    # validation and generation only see the selected tables
    assert validate_kql("SecurityEvent | where TimeGenerated > ago(1d)", prof)["status"] == "error"
    assert validate_kql("SigninLogs | where TimeGenerated > ago(1d) | project UserPrincipalName", prof)["status"] == "ok"

    # re-apply replaces files; scope all brings customer.md tables back
    res = cs.apply(store, "contoso", {"defender-xdr": ["DeviceProcessEvents"]}, "all")
    assert res["written"] == ["catalog-defender-xdr.md"]
    assert not (customers_dir / "contoso" / "schemas" / "catalog-sentinel.md").exists()
    prof = store.load("contoso")
    assert prof.schema_scope == "all" and "DeviceProcessEvents" in prof.tables and len(prof.tables) > 1
    assert cs.selection(store, "contoso")["selection"] == {"defender-xdr": ["DeviceProcessEvents"]}


def test_apply_rejects_bad_input(store, cat_path):
    from app.security import InputError
    cs = CatalogStore(cat_path)
    with pytest.raises(InputError):
        cs.apply(store, "contoso", {"nope": ["X"]}, "selected")
    with pytest.raises(InputError):
        cs.apply(store, "contoso", {"sentinel": ["NotATable"]}, "selected")
    with pytest.raises(InputError):
        cs.apply(store, "contoso", {}, "selected")


def test_set_setting_adds_section(store, customers_dir):
    store.create("Northwind")
    store.set_setting("northwind", "schema_scope", "selected")
    store.set_setting("northwind", "schema_scope", "all")
    text = (customers_dir / "northwind" / "customer.md").read_text()
    assert text.count("schema_scope") == 1 and "- schema_scope: all" in text


def test_custom_sections_saved_and_microsoft_protected(cat_path):
    cs = CatalogStore(cat_path)
    assert "MyApp_CL" in cs.custom_markdown()
    cs.save_custom("## Schema: Firewall\nId: fw\nOrigin: custom\n\n### Fw_CL\n| Column | Type | Description |\n"
                   "|---|---|---|\n| TimeGenerated | datetime | |\n| SrcIp_s | string | |\n")
    cat = cs.load()
    assert set(cat.schemas) == {"sentinel", "defender-xdr", "fw"}
    from app.security import InputError
    with pytest.raises(InputError):
        cs.save_custom("## Schema: X\nId: sentinel\nOrigin: custom\n")


def test_fetch_only_microsoft_learn():
    assert _check_url("https://learn.microsoft.com/en-us/x")
    for bad in ("http://learn.microsoft.com/x", "https://evil.example/x", "https://learn.microsoft.com.evil.io/x"):
        with pytest.raises(ValueError):
            _check_url(bad)


class FakeFetcher(Fetcher):
    workers = 2

    def __init__(self):
        self.pages = {
            "https://learn.microsoft.com/idx": '<h3 id="security">Security</h3><ul><li><a href="tables/signinlogs">SigninLogs</a></li>'
                                               '<li><a href="tables/broken">Broken</a></li></ul><h3 id="vm">VM</h3>',
            "https://learn.microsoft.com/tables/signinlogs": '<table><tr><th>Column</th><th>Type</th><th>Description</th></tr>'
                                                            '<tr><td>UserPrincipalName</td><td>string</td><td>upn</td></tr></table>',
        }

    def get(self, url):
        if url not in self.pages:
            raise RuntimeError("HTTP 404")
        return self.pages[url]


def test_refresh_keeps_custom_and_reports_errors(cat_path):
    src = Source("sentinel", "Microsoft Sentinel (Log Analytics)", "https://learn.microsoft.com/idx", "TimeGenerated", "azure-monitor")
    res = refresh_catalog(cat_path, [src], fetcher=FakeFetcher())
    assert len(res["errors"]) == 1 and "Broken" in res["errors"][0]
    cat = parse_catalog(cat_path.read_text())
    signin = cat.schemas["sentinel"].tables["SigninLogs"]
    assert [c.name for c in signin.columns] == ["UserPrincipalName", "TimeGenerated"]  # standard column added
    assert "SecurityEvent" in cat.schemas["sentinel"].tables  # failed/unlisted kept from previous catalog
    assert "custom" in cat.schemas and "defender-xdr" not in cat.schemas


def test_api_selection_flow(customers_dir, tmp_path, cat_path):
    from app.main import create_app
    s = dataclasses.replace(load_settings(), customers_dir=customers_dir, data_dir=tmp_path / "data",
                            catalog_path=cat_path, catalog_fetch_enabled=False)
    c = TestClient(create_app(s))
    cat = c.get("/api/catalog").json()
    assert [x["id"] for x in cat["schemas"]] == ["sentinel", "defender-xdr", "custom"] and not cat["fetch_enabled"]
    assert c.post("/api/catalog/refresh").status_code == 403
    assert c.get("/api/catalog/tables/sentinel/SigninLogs").json()["columns"][1]["name"] == "UserPrincipalName"
    r = c.put("/api/customers/fabrikam/catalog-selection", json={"selection": {"defender-xdr": ["DeviceProcessEvents"]}})
    assert r.status_code == 200, r.text
    assert c.get("/api/customers/fabrikam").json()["schema_scope"] == "selected"
    assert [t["name"] for t in c.get("/api/customers/fabrikam").json()["tables"]] == ["DeviceProcessEvents"]
    assert c.get("/api/customers/contoso/catalog-selection").json()["selection"] == {}  # other customer untouched
    assert any(e["action"] == "customer.schema.apply" for e in c.get("/api/customers/fabrikam/audit").json())


def test_categories_follow_defender_groups():
    from app.catalog.categories import categorize
    assert categorize("AlertInfo") == "Alerts & behaviors"
    assert categorize("IdentityLogonEvents") == categorize("SigninLogs") == "Apps & identities"
    assert categorize("EmailEvents") == categorize("UrlClickEvents") == "Email & collaboration"
    assert categorize("DeviceProcessEvents") == categorize("SecurityEvent") == "Devices"
    assert categorize("DeviceTvmSoftwareInventory") == "Threat & vulnerability management"
    assert categorize("ExposureGraphNodes") == "Exposure management"
    assert categorize("Contoso_CL") == "Other"
    md = ("## Schema: X\nId: x\nOrigin: custom\n\n### Contoso_CL\nCategory: Network\n\n"
          "| Column | Type | Description |\n|---|---|---|\n| TimeGenerated | datetime | |\n")
    t = parse_catalog(md).schemas["x"].tables["Contoso_CL"]
    assert t.group == "Network" and "Category: Network" in render_table(t)
