from app.investigation.classifier import classify, map_tables
from app.investigation.parser import parse_log
from app.observables.extract import extract_observables
from tests.conftest import example


def test_parse_json_csv_kv_text():
    assert parse_log('{"a": {"b": 1}}').fields["a.b"] == "1"
    assert parse_log('[{"x":1},{"x":2}]').records == 2
    assert parse_log('{"value":[{"x":1}]}').fields["x"] == "1"
    assert parse_log("a,b,c\n1,2,3\n4,5,6").format == "csv"
    kv = parse_log("src=10.0.0.1 dst=8.8.8.8 user=bob action=allow")
    assert kv.format == "key-value" and kv.get("user") == "bob"
    assert parse_log("just some free text").format == "text"


def test_observables_with_tags_and_defang():
    obs = extract_observables("login from 185.220.101.47 and 10.1.2.3 to hxxps://evil[.]example[.]com/x by bob@contoso.com "
                              "hash 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08 C:\\Temp\\a.exe")
    by = {(o["type"], o["value"]): o for o in obs}
    assert "external" in by[("ip", "185.220.101.47")]["tags"]
    assert "internal" in by[("ip", "10.1.2.3")]["tags"]
    assert ("url", "https://evil.example.com/x") in by
    assert ("domain", "evil.example.com") in by
    assert ("email", "bob@contoso.com") in by
    assert ("sha256", "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08") in by
    assert ("file", "a.exe") in by
    assert not any(o["type"] == "domain" and o["value"].endswith(".exe") for o in obs)


def test_key_aware_extraction():
    parsed = parse_log('{"DeviceName":"WS-01","AccountUpn":"a@b.com","InitiatingProcessFileName":"winword.exe"}')
    obs = extract_observables('{"DeviceName":"WS-01"}', parsed.fields)
    types = {(o["type"], o["value"]) for o in obs}
    assert ("hostname", "WS-01") in types and ("user", "a@b.com") in types and ("process", "winword.exe") in types


def test_classify_and_map_signin(contoso, fabrikam):
    raw = example("contoso", "failed-signin.json")
    p = parse_log(raw)
    types = classify(raw, p)
    assert types[0]["type"] == "entra_signin" and types[0]["confidence"] == "high"
    assert map_tables(contoso, p, types)[0]["table"] == "SigninLogs"
    # the same event maps to Fabrikam's own sign-in table
    assert map_tables(fabrikam, p, types)[0]["table"] == "AADSignInEventsBeta"


def test_classify_process_and_email():
    raw = example("contoso", "encoded-powershell.json")
    assert classify(raw, parse_log(raw))[0]["type"] == "process_execution"
    raw = example("fabrikam", "phishing-email.csv")
    assert {t["type"] for t in classify(raw, parse_log(raw))} & {"phishing", "email"}
