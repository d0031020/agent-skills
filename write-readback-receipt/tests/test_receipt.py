"""Verify local reconciliation, CLI boundaries, privacy and saved receipts."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.readback_receipt import InvalidInput, reconcile, render_human

SCENARIOS = [
    ("all-verified-crm", "verified", 0),
    ("fake-success", "missing", 1),
    ("wrong-id", "wrong_id", 1),
    ("field-mismatch", "mismatch", 1),
    ("stale-readback", "stale", 1),
    ("pending-readback", "pending", 1),
    ("mixed", None, 1),
]


def fixture(name="all-verified-crm"):
    folder = ROOT / "examples" / name
    return tuple(json.loads((folder / filename).read_text())
                 for filename in ("expected.json", "observed.json"))


def cli(*args):
    return subprocess.run([sys.executable, str(ROOT / "tools/readback_receipt.py"), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, check=False)


def example_cli(name, *args):
    folder = ROOT / "examples" / name
    return cli("--expected", folder / "expected.json", "--observed", folder / "observed.json", *args)


@pytest.mark.parametrize("name,status,code", SCENARIOS)
def test_each_status_and_overall_rule(name, status, code):
    report = reconcile(*fixture(name))
    assert report["status"] == ("pass" if code == 0 else "fail")
    if status:
        assert report["receipts"][0]["status"] == status
    else:
        assert [item["status"] for item in report["receipts"]] == [
            "verified", "mismatch", "missing", "wrong_id", "stale", "pending"]
        assert set(report["counts"].values()) == {1}
    assert (report["status"] == "pass") == all(
        item["status"] == "verified" for item in report["receipts"])


@pytest.mark.parametrize("name,status,code", SCENARIOS)
def test_cli_and_saved_receipts(name, status, code):
    human = example_cli(name)
    machine = example_cli(name, "--json")
    assert human.returncode == machine.returncode == code
    assert not human.stderr and not machine.stderr
    assert json.loads(machine.stdout) == reconcile(*fixture(name))
    assert human.stdout.endswith(machine.stdout)
    folder = ROOT / "examples" / name
    assert human.stdout == (folder / "receipt.txt").read_text()
    assert machine.stdout == (folder / "receipt.json").read_text()


@pytest.mark.parametrize("name,status,code", SCENARIOS)
@pytest.mark.parametrize("show", [[], ["company"], ["company", "status", "private_note", "email"]])
def test_masking_all_output_paths(name, status, code, show):
    expected, observed = fixture(name)
    for write in expected["writes"]:
        write["required_fields"]["secret"] = "EXPECTED_PRIVATE_SENTINEL"
    for record in observed["records"] or []:
        record["fields"]["secret"] = "OBSERVED_PRIVATE_SENTINEL"
    report = reconcile(expected, observed, show_fields=show)
    output = render_human(report) + json.dumps(report)
    for secret in ("EXPECTED_PRIVATE_SENTINEL", "OBSERVED_PRIVATE_SENTINEL",
                   "fictional.person@example.com", "Illustrative private note; do not include in receipts."):
        assert secret not in output
    for write in expected["writes"]:
        for key, value in write["required_fields"].items():
            if key not in show:
                assert value not in output
    if "company" in show:
        assert "Acme Example" in output


@pytest.mark.parametrize("mode", [[], ["--json"]])
def test_cli_masking_and_allowlist(mode):
    result = example_cli("field-mismatch", "--show-fields", "company,email,private_note", *mode)
    assert result.returncode == 1
    assert "Acme Example" in result.stdout
    for hidden in ('"inactive"', '"active"', "fictional.person@example.com", "Illustrative private note"):
        assert hidden not in result.stdout
    shown = example_cli("field-mismatch", "--show-fields", "status", *mode)
    assert '"inactive"' in shown.stdout and '"active"' in shown.stdout


def test_differences_list_values_and_missing_fields():
    expected, observed = fixture()
    observed["records"][0]["fields"].pop("company")
    observed["records"][0]["fields"]["status"] = "inactive"
    item = reconcile(expected, observed, show_fields=["company", "status"])["receipts"][0]
    assert item["status"] == "mismatch"
    assert item["differences"] == [
        {"field": "company", "kind": "missing", "expected": "Acme Example"},
        {"field": "status", "kind": "value", "expected": "active", "observed": "inactive"}]


@pytest.mark.parametrize("wanted,actual,status", [
    (True, 1, "mismatch"), (False, 0, "mismatch"), (1, "1", "mismatch"),
    (1, 1.0, "verified"), (None, None, "verified"), ("Acme Example", "acme example", "mismatch")])
def test_json_scalar_equality(wanted, actual, status):
    expected, observed = fixture()
    expected["writes"][0]["required_fields"] = {"value": wanted}
    observed["records"][0]["fields"] = {"value": actual}
    assert reconcile(expected, observed)["receipts"][0]["status"] == status


def test_missing_is_distinct_from_null():
    expected, observed = fixture()
    expected["writes"][0]["required_fields"] = {"value": None}
    observed["records"][0]["fields"] = {}
    assert reconcile(expected, observed)["receipts"][0]["status"] == "mismatch"


def test_present_id_takes_precedence_over_alternative():
    expected, observed = fixture("field-mismatch")
    other = copy.deepcopy(observed["records"][0])
    other["id"] = "crm-alternative"
    other["fields"]["status"] = "active"
    observed["records"].append(other)
    assert reconcile(expected, observed)["receipts"][0]["status"] == "mismatch"


def test_wrong_id_candidates_are_sorted_and_require_all_fields():
    expected, observed = fixture("wrong-id")
    observed["records"] *= 2
    observed["records"][1] = copy.deepcopy(observed["records"][1])
    observed["records"][1]["id"] = "crm-another"
    assert reconcile(expected, observed)["receipts"][0]["candidate_ids"] == ["crm-another", "crm-other"]
    for record in observed["records"]:
        record["fields"].pop("status")
    assert reconcile(expected, observed)["receipts"][0]["status"] == "missing"


@pytest.mark.parametrize("records", [None, []])
def test_missing_evidence_never_passes(records):
    expected, observed = fixture()
    observed["records"] = records
    report = reconcile(expected, observed)
    assert report["status"] == "fail"
    assert report["counts"]["verified"] == 0


def test_pending_id_overrides_matching_content_elsewhere():
    expected, observed = fixture("wrong-id")
    observed["pending_ids"] = [expected["writes"][0]["id"]]
    assert reconcile(expected, observed)["receipts"][0]["status"] == "pending"


@pytest.mark.parametrize("read_at,snapshot,now,max_age,status", [
    ("10:01:00", "10:01:00", None, 0, "verified"),
    ("10:00:00", "10:01:00", None, 60, "verified"),
    ("09:59:59", "10:01:00", None, 300, "stale"),
    ("10:00:00", "10:01:00", None, 59, "stale"),
    ("10:01:00", "10:01:00", "10:06:00", 300, "verified"),
    ("10:01:00", "10:01:00", "10:06:00.000001", 300, "stale"),
    ("10:00:00.123456", "10:01:00", None, 60, "verified"),
])
def test_freshness_boundaries(read_at, snapshot, now, max_age, status):
    expected, observed = fixture()
    observed["records"][0]["read_at"] = f"2030-01-01T{read_at}Z"
    observed["snapshot_at"] = f"2030-01-01T{snapshot}Z"
    report = reconcile(expected, observed, max_age=max_age,
                       now=f"2030-01-01T{now}Z" if now else None)
    assert report["receipts"][0]["status"] == status


@pytest.mark.parametrize("name", ["fake-success", "wrong-id", "field-mismatch"])
def test_stale_snapshot_never_proves_identity_or_absence(name):
    expected, observed = fixture(name)
    for write in expected["writes"]:
        write["written_at"] = "2030-01-01T10:02:00Z"
    report = reconcile(expected, observed)
    assert report["status"] == "fail"
    assert report["receipts"][0]["status"] == "stale"


def test_stale_wrong_id_candidates_and_fresh_alternative():
    expected, observed = fixture("wrong-id")
    observed["records"][0]["read_at"] = "2030-01-01T09:59:00Z"
    assert reconcile(expected, observed)["receipts"][0]["status"] == "stale"
    other = copy.deepcopy(observed["records"][0])
    other.update(id="crm-fresh", read_at=observed["snapshot_at"])
    observed["records"].append(other)
    item = reconcile(expected, observed)["receipts"][0]
    assert item["status"] == "wrong_id" and item["candidate_ids"] == ["crm-fresh"]


@pytest.mark.parametrize("mode", [[], ["--json"]])
def test_deterministic_cli(mode):
    a = example_cli("mixed", "--now", "2030-01-01T10:02:00Z", *mode)
    b = example_cli("mixed", "--now", "2030-01-01T10:02:00Z", *mode)
    assert a.returncode == b.returncode == 1 and a.stdout == b.stdout


@pytest.mark.parametrize("target,key,value", [
    ("expected", "writes", []), ("expected", "writes", None),
    ("expected", "extra", "PRIVATE_SENTINEL"), ("observed", "records", {}),
    ("observed", "snapshot_at", "2030-02-30T10:01:00Z"),
    ("observed", "snapshot_at", "2030-01-01T10:01:00+00:00"),
    ("observed", "snapshot_at", "2030-01-01T10:01:00.1234567Z"),
    ("observed", "pending_ids", "crm-acme"),
])
def test_invalid_structure(target, key, value):
    expected, observed = fixture()
    (expected if target == "expected" else observed)[key] = value
    with pytest.raises(InvalidInput):
        reconcile(expected, observed)


@pytest.mark.parametrize("change", [
    "duplicate_expected", "duplicate_observed", "pending_overlap", "duplicate_pending",
    "null_with_pending", "empty_required", "nested_field", "invalid_id", "invalid_field",
    "future_read", "unknown_record_key", "missing_write_key", "nonfinite_field",
])
def test_invalid_semantic_constraints(change):
    expected, observed = fixture()
    if change == "duplicate_expected": expected["writes"] *= 2
    elif change == "duplicate_observed": observed["records"] *= 2
    elif change == "pending_overlap": observed["pending_ids"] = ["crm-acme"]
    elif change == "duplicate_pending": observed["pending_ids"] = ["crm-pending"] * 2
    elif change == "null_with_pending": observed.update(records=None, pending_ids=["crm-pending"])
    elif change == "empty_required": expected["writes"][0]["required_fields"] = {}
    elif change == "nested_field": observed["records"][0]["fields"]["nested"] = {"secret": "PRIVATE_SENTINEL"}
    elif change == "invalid_id": expected["writes"][0]["id"] = "../private"
    elif change == "invalid_field": observed["records"][0]["fields"]["bad\n"] = "PRIVATE_SENTINEL"
    elif change == "future_read": observed["records"][0]["read_at"] = "2030-01-01T10:02:00Z"
    elif change == "unknown_record_key": observed["records"][0]["extra"] = "PRIVATE_SENTINEL"
    elif change == "missing_write_key": del expected["writes"][0]["written_at"]
    elif change == "nonfinite_field": observed["records"][0]["fields"]["amount"] = float("inf")
    with pytest.raises(InvalidInput):
        reconcile(expected, observed)


@pytest.mark.parametrize("raw", ['{', '{"writes":[],"writes":[]}', '{"writes":NaN}',
                                 '{"writes":Infinity}', 'null', '[]', '"PRIVATE_SENTINEL"'])
@pytest.mark.parametrize("mode", [[], ["--json"]])
def test_invalid_json_cli_exit_two(tmp_path, raw, mode):
    path = tmp_path / "bad.json"
    path.write_text(raw)
    result = cli("--expected", path, "--observed", ROOT / "examples/all-verified-crm/observed.json", *mode)
    assert result.returncode == 2
    assert "invalid" in result.stdout and "PRIVATE_SENTINEL" not in result.stdout + result.stderr
    if mode:
        assert json.loads(result.stdout)["status"] == "invalid"


@pytest.mark.parametrize("args", [
    ["--max-age", "-1"], ["--max-age", "nan"], ["--max-age", "inf"],
    ["--max-age", "PRIVATE_SENTINEL"], ["--now", "PRIVATE_SENTINEL"],
    ["--now", "2030-01-01T10:00:59Z"], ["--show-fields", "company,,status"],
    ["--show-fields", "bad field"], ["--unexpected", "PRIVATE_SENTINEL"],
])
def test_invalid_options_cli_exit_two(args):
    result = example_cli("all-verified-crm", *args, "--json")
    assert result.returncode == 2 and json.loads(result.stdout)["status"] == "invalid"
    assert "PRIVATE_SENTINEL" not in result.stdout + result.stderr


def test_missing_files_arguments_and_parent_traversal(tmp_path):
    observed = ROOT / "examples/all-verified-crm/observed.json"
    for path in (tmp_path / "absent.json", "examples/all-verified-crm/../all-verified-crm/expected.json"):
        assert cli("--expected", path, "--observed", observed, "--json").returncode == 2
    assert cli("--json").returncode == 2
    assert cli("--help").returncode == 0


@pytest.mark.parametrize("wanted,actual,code", [
    ("9007199254740992.1", "9007199254740992.2", 2),
    ("0.10000000000000001", "0.1", 2),
    ("1e-999", "0", 2), ("1e999", "1", 2),
    ("0.1", "0.10", 0), ("1e23", "100000000000000000000000", 0),
    ("0.1", "0.2", 1),
])
def test_decimal_literals_never_match_due_to_rounding(tmp_path, wanted, actual, code):
    expected, observed = fixture()
    expected["writes"][0]["required_fields"] = {"amount": "NUMBER_PLACEHOLDER"}
    observed["records"][0]["fields"] = {"amount": "NUMBER_PLACEHOLDER"}
    paths = []
    for name, data, literal in [("expected", expected, wanted), ("observed", observed, actual)]:
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(data).replace('"NUMBER_PLACEHOLDER"', literal))
        paths.append(path)
    result = cli("--expected", paths[0], "--observed", paths[1], "--json")
    assert result.returncode == code
    assert json.loads(result.stdout)["status"] == {0: "pass", 1: "fail", 2: "invalid"}[code]


def test_invalid_utf8_is_invalid_without_echo(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_bytes(b'\xffPRIVATE_SENTINEL')
    result = cli("--expected", path, "--observed", path, "--json")
    assert result.returncode == 2
    assert "PRIVATE_SENTINEL" not in result.stdout + result.stderr
