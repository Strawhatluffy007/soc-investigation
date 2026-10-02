from app.investigation.engine import analyze
from app.kql.generator import kql_str
from app.kql.validator import LOCAL_NOTE, validate_kql
from tests.conftest import example


def test_generated_queries_use_customer_fields(contoso, fabrikam):
    raw = example("contoso", "failed-signin.json")
    c = analyze(contoso, raw)["kql_queries"]
    f = analyze(fabrikam, raw)["kql_queries"]
    assert c and f
    assert all("TimeGenerated" in q["query"] for q in c)
    assert any(q["query"].startswith("SigninLogs") for q in c)
    assert all("TimeGenerated" not in q["query"] for q in f)
    assert any(q["query"].startswith("AADSignInEventsBeta") and "AccountUpn" in q["query"] for q in f)
    for q in c + f:
        assert q["validation"]["status"] == "ok", (q["query"], q["validation"])
        assert q["validation"]["note"] == LOCAL_NOTE



def test_value_escaping():
    assert kql_str('a"b\\c') == '"a\\"b\\\\c"'


def test_validator_flags_unknown_table_and_field(contoso, fabrikam):
    v = validate_kql("SigninLogs | where TimeGenerated > ago(1d) | where Foo == 1", fabrikam)
    assert v["status"] == "error" and any("SigninLogs" in e for e in v["errors"])
    v = validate_kql("SigninLogs | where TimeGenerated > ago(1d) | where MadeUpField == 1", contoso)
    assert v["status"] == "warning" and "MadeUpField" in v["unknown_fields"]


def test_validator_syntax(contoso):
    assert validate_kql("SigninLogs | where TimeGenerated > ago(1d) | where (IPAddress == \"x\"", contoso)["status"] == "error"
    assert validate_kql("SigninLogs | where TimeGenerated > ago(1d) |", contoso)["status"] == "error"
    assert validate_kql("SigninLogs | wher TimeGenerated > ago(1d)", contoso)["status"] == "error"
    assert validate_kql('SigninLogs | where TimeGenerated > ago(1d) | where IPAddress == "unterminated', contoso)["status"] == "error"


def test_validator_time_filter_and_aliases(contoso):
    v = validate_kql("SigninLogs | where UserPrincipalName =~ 'a'", contoso)
    assert any("time filter" in w for w in v["warnings"])
    q = ('let ip = "1.2.3.4";\nSigninLogs\n| where TimeGenerated > ago(7d)\n| where IPAddress == ip\n'
         '| summarize Fails = countif(ResultType != "0"), Users = dcount(UserPrincipalName) by IPAddress, bin(TimeGenerated, 1h)\n'
         '| where Fails > 5\n| order by Fails desc')
    assert validate_kql(q, contoso)["status"] == "ok", validate_kql(q, contoso)


def test_validator_join(contoso):
    q = ("DeviceProcessEvents | where TimeGenerated > ago(1d)\n| join kind=inner (DeviceNetworkEvents | where TimeGenerated > ago(1d)) "
         "on DeviceName\n| project TimeGenerated, DeviceName, RemoteIP")
    v = validate_kql(q, contoso)
    assert v["tables"] == ["DeviceProcessEvents", "DeviceNetworkEvents"] and v["status"] == "ok", v


def test_forbidden_table(fabrikam, contoso):
    # AuditLogs is listed as forbidden for Fabrikam
    v = validate_kql("AuditLogs | where TimeGenerated > ago(1d)", fabrikam)
    assert any("not permitted" in e or "not in" in e for e in v["errors"])
