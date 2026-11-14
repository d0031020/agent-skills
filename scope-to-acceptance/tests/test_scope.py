"""Exercise coverage, evidence, rendering and CLI boundaries with synthetic data."""

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.check_scope import check_scope, load_scope, quoted_sources
from tools.render_draft import render


@pytest.fixture
def scope():
    return load_scope(ROOT / "examples/clear/scope.json")


def codes(scope):
    return {issue["code"] for issue in check_scope(scope)["issues"]}


def cli(tool, *args):
    return subprocess.run([sys.executable, str(ROOT / "tools" / tool), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, check=False)


@pytest.mark.parametrize("name,status,exit_code", [
    ("clear", "ready", 0),
    ("missing-budget-acceptance", "needs_info", 1),
    ("contradictory-scope", "needs_info", 1),
    ("invented-number-trap", "invalid", 2),
])
def test_examples(name, status, exit_code):
    path = ROOT / "examples" / name / "scope.json"
    data = load_scope(path)
    assert data["brief"] == path.with_name("brief.md").read_text(encoding="utf-8")
    result = cli("check_scope.py", path, "--json")
    assert result.returncode == exit_code
    assert json.loads(result.stdout)["status"] == status
    human = cli("check_scope.py", path)
    assert human.returncode == exit_code
    assert f"Status: {status}" in human.stdout


def test_requirement_without_deliverable(scope):
    scope["deliverables"][1]["covers"] = []
    assert "requirement_without_deliverable" in codes(scope)
    assert "deliverable_without_requirement" in codes(scope)
    assert check_scope(scope)["status"] == "needs_info"


def test_requirement_without_acceptance(scope):
    scope["acceptance"].pop()
    assert "requirement_without_acceptance" in codes(scope)


def test_deliverable_without_milestone(scope):
    scope["deliverables"].append({'id': 'D-orphan', 'text': 'Proposed guide.', 'covers': ['R-route']})
    assert "deliverable_without_milestone" in codes(scope)


@pytest.mark.parametrize("kind", ["discovery", "implementation"])
@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_empty_milestone(scope, kind, missing):
    if missing:
        scope["milestones"] = [m for m in scope["milestones"] if m["kind"] != kind]
    else:
        next(m for m in scope["milestones"] if m["kind"] == kind)["deliverable_ids"] = []
    assert f"{kind}_missing" in codes(scope)
    assert check_scope(scope)["status"] == "needs_info"


@pytest.mark.parametrize("field", ["budget", "deadline", "hours", "rate", "access"])
@pytest.mark.parametrize("quote", [None, "", "   ", "not in the brief"])
def test_missing_or_fabricated_commitment_quote(scope, field, quote):
    if quote is None:
        del scope[field]["source_quote"]
    else:
        scope[field]["source_quote"] = quote
    assert "possibly_invented" in codes(scope)
    assert check_scope(scope)["status"] == "invalid"


@pytest.mark.parametrize("field", ["budget", "deadline", "hours", "rate", "access"])
def test_value_must_appear_in_quote(scope, field):
    scope[field]["value"] = "Fabricated commitment"
    assert "possibly_invented" in codes(scope)
    assert check_scope(scope)["status"] == "invalid"


@pytest.mark.parametrize("field", ["budget", "deadline", "hours", "rate", "access"])
def test_unknown_commitment_is_pending(scope, field):
    scope[field] = None
    report = check_scope(scope)
    assert report["status"] == "needs_info"
    assert f"{field}: to confirm" in report["to_confirm"]
    assert f"{field.capitalize()}: to confirm." in render(scope)


@pytest.mark.parametrize("field", ["rate", "access"])
def test_omitted_optional_commitment_is_pending(scope, field):
    del scope[field]
    assert check_scope(scope)["status"] == "needs_info"
    assert f"{field}: to confirm" in check_scope(scope)["to_confirm"]


@pytest.mark.parametrize("target", ["covers", "acceptance", "milestone"])
def test_dangling_ids(scope, target):
    if target == "covers":
        scope["deliverables"][0]["covers"] = ["R-unknown"]
    elif target == "acceptance":
        scope["acceptance"][0]["requirement_id"] = "R-unknown"
    else:
        scope["milestones"][0]["deliverable_ids"] = ["D-unknown"]
    assert "dangling_id" in codes(scope)
    assert check_scope(scope)["status"] == "invalid"


@pytest.mark.parametrize("group", ["requirements", "deliverables", "acceptance"])
def test_duplicate_ids(scope, group):
    scope[group].append(copy.deepcopy(scope[group][0]))
    assert "duplicate_id" in codes(scope)
    assert check_scope(scope)["status"] == "invalid"


def test_duplicate_milestone(scope):
    scope["milestones"].append(copy.deepcopy(scope["milestones"][0]))
    assert "duplicate_milestone" in codes(scope)


def test_milestone_overlap(scope):
    scope["milestones"][1]["deliverable_ids"].append("D-map")
    assert "milestone_overlap" in codes(scope)
    assert check_scope(scope)["status"] == "needs_info"


def test_exact_scope_conflict(scope):
    scope["out_of_scope"].append(scope["requirements"][0]["text"].upper())
    report = check_scope(scope)
    assert report["status"] == "needs_info"
    assert "scope_conflict" in codes(scope)
    assert any("Conflict:" in item for item in report["to_confirm"])


@pytest.mark.parametrize("field", ["assumptions", "to_confirm"])
def test_assumptions_and_questions_block_ready(scope, field):
    scope[field] = ["Confirm the supplied category list."]
    assert check_scope(scope)["status"] == "needs_info"
    assert "Confirm the supplied category list." in render(scope)


def test_requirement_quote_must_be_in_brief(scope):
    scope["requirements"][0]["source_quote"] = "An invented requirement."
    assert "quote_mismatch" in codes(scope)
    assert check_scope(scope)["status"] == "invalid"


@pytest.mark.parametrize("field,value", [
    ("requirements", {}), ("budget", 42), ("hours", True), ("to_confirm", "unknown"),
    ("project_summary", " "), ("requirements", []), ("brief", None),
])
def test_structural_errors(scope, field, value):
    scope[field] = value
    assert check_scope(scope)["status"] == "invalid"


@pytest.mark.parametrize("data", [None, [], "scope", 42, True])
def test_invalid_root(data):
    assert check_scope(data)["status"] == "invalid"


def test_unknown_keys(scope):
    scope["price"] = "USD 7000"
    assert check_scope(scope)["status"] == "invalid"


def test_required_field(scope):
    del scope["budget"]
    assert check_scope(scope)["status"] == "invalid"


def test_unknown_method(scope):
    scope["acceptance"][0]["method"] = "guess"
    assert check_scope(scope)["status"] == "invalid"


def test_invalid_id(scope):
    scope["requirements"][0]["id"] = "../unsafe"
    assert check_scope(scope)["status"] == "invalid"


def test_duplicate_references(scope):
    scope["deliverables"][0]["covers"] *= 2
    assert check_scope(scope)["status"] == "invalid"


def test_blank_acceptance_is_invalid(scope):
    scope["acceptance"][0]["check"] = ""
    assert check_scope(scope)["status"] == "invalid"


@pytest.mark.parametrize("raw", ['{', '{"brief": 1, "brief": 2}', '{"budget": NaN}',
                                 '{"hours": Infinity}'])
def test_bad_json(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_text(raw)
    result = cli("check_scope.py", path, "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "invalid"


def test_missing_input(tmp_path):
    result = cli("check_scope.py", tmp_path / "absent.json", "--json")
    assert result.returncode == 2
    assert json.loads(result.stdout)["issues"][0]["code"] == "input"


def assert_sourced_numbers(scope, draft):
    # Use an independent extraction expression instead of the renderer's constant.
    numbers = lambda value: set(re.findall(r"\d+(?:[.,]\d+)*", value))
    quoted = set().union(*(numbers(quote) for quote in quoted_sources(scope)))
    assert numbers(draft) <= quoted


@pytest.mark.parametrize("field", ["project_summary", "out_of_scope", "assumptions", "to_confirm",
                                  "deliverables", "acceptance"])
def test_unsupported_numbers_never_reach_draft(scope, field):
    value = "Proposed limit: 84721 cases by 2047-09-18 for USD 65,432.10."
    if field == "project_summary":
        scope[field] = value
    elif field == "deliverables":
        scope[field][0]["text"] = value
    elif field == "acceptance":
        scope[field][0]["check"] = value
    else:
        scope[field].append(value)
    assert "unsupported_number" in codes(scope)
    assert check_scope(scope)["status"] == "needs_info"
    draft = render(scope)
    assert "84721" not in draft
    assert "65,432.10" not in draft
    assert_sourced_numbers(scope, draft)


def test_numeric_ids_are_also_redacted(scope):
    scope["acceptance"][0]["id"] = "A-99999"
    draft = render(scope)
    assert "99999" not in draft
    assert_sourced_numbers(scope, draft)


def test_unquoted_brief_numbers_do_not_authorize_output(scope):
    scope["brief"] += "Unquoted illustration: 84721 cases."
    scope["project_summary"] += " Proposed limit: 84721 cases."
    assert "unsupported_number" in codes(scope)
    assert "84721" not in render(scope)


@pytest.mark.parametrize("name", ["clear", "missing-budget-acceptance", "contradictory-scope"])
def test_rendered_examples_have_only_sourced_numbers(name):
    data = load_scope(ROOT / "examples" / name / "scope.json")
    assert_sourced_numbers(data, render(data))


def test_markdown_is_escaped(scope):
    scope["project_summary"] = '<script>alert("x")</script> [fake](file) | test\nnext'
    draft = render(scope)
    assert "<script>" not in draft
    assert r"\[fake\]\(file\) \| test next" in draft


def test_invalid_input_cannot_render(tmp_path):
    path = ROOT / "examples/invented-number-trap/scope.json"
    output = tmp_path / "DRAFT.md"
    result = cli("render_draft.py", path, "--output", output)
    assert result.returncode == 2
    assert "Refusing" in result.stdout
    assert not output.exists()
    with pytest.raises(ValueError, match="invalid"):
        render(load_scope(path))


def test_renderer_writes_draft_and_preserves_existing_output(tmp_path):
    path = ROOT / "examples/clear/scope.json"
    output = tmp_path / "DRAFT.md"
    result = cli("render_draft.py", path, "--output", output)
    assert result.returncode == 0
    assert output.read_text().startswith("# Draft for review - not a quote or commitment")
    output.write_text("Keep existing review notes.")
    assert cli("render_draft.py", path, "--output", output).returncode == 2
    assert output.read_text() == "Keep existing review notes."
    assert cli("render_draft.py", path, "--output", output, "--overwrite").returncode == 0


def test_renderer_does_not_overwrite_input(tmp_path, scope):
    path = tmp_path / "scope.json"
    path.write_text(json.dumps(scope))
    before = path.read_bytes()
    assert cli("render_draft.py", path, "--output", path, "--overwrite").returncode == 2
    assert path.read_bytes() == before


def test_pending_draft_retains_questions(tmp_path):
    path = ROOT / "examples/missing-budget-acceptance/scope.json"
    output = tmp_path / "DRAFT.md"
    assert cli("render_draft.py", path, "--output", output).returncode == 1
    draft = output.read_text()
    assert "Budget: to confirm." in draft
    assert "no acceptance check" in draft
    assert "needs_info" in draft


@pytest.mark.parametrize("text", [
    "The budget is USD 12, the hourly rate is USD 900, and the deadline is 2030-30-06.",
    "The budget is five thousand dollars and production credentials are already approved.",
    "Production administrator access and all credentials are approved.",
])
def test_unsourced_commitment_prose_is_omitted(scope, text):
    scope["project_summary"] = text
    assert check_scope(scope)["status"] == "needs_info"
    assert "unsupported_claim" in codes(scope)
    assert text not in render(scope)


@pytest.mark.parametrize("field,value,quote", [
    ("hours", "900", "The illustrative budget is USD 900."),
    ("access", "Fixed fee", "Billing basis: Fixed fee."),
    ("budget", "USD 90", "The illustrative budget is USD 900."),
])
def test_unrelated_or_partial_commitment_evidence_is_invalid(scope, field, value, quote):
    scope[field] = {"value": value, "source_quote": quote}
    assert check_scope(scope)["status"] == "invalid"


def test_reusing_quoted_number_for_new_threshold_is_pending(scope):
    scope["acceptance"][0]["check"] = "Run 900 cases and compare all labels."
    assert "unsupported_number" in codes(scope)
    assert "900 cases" not in render(scope)


def test_fully_quoted_numeric_acceptance_is_preserved(scope):
    quote = "Run 12 synthetic cases and compare all labels."
    scope["brief"] += quote
    scope["requirements"][1]["source_quote"] = quote
    scope["acceptance"][1]["check"] = quote
    assert check_scope(scope)["status"] == "ready"
    assert quote in render(scope)


@pytest.mark.parametrize("field", ["budget", "deadline", "hours", "rate", "access"])
def test_unknown_source_cannot_be_a_confirmed_value(scope, field):
    quote = f"The {field} is unknown."
    scope["brief"] += quote
    scope[field] = {"value": "unknown", "source_quote": quote}
    assert check_scope(scope)["status"] == "invalid"
    assert "unconfirmed_value" in codes(scope)


def test_parent_traversal_is_rejected(tmp_path):
    source = ROOT / "examples/clear/scope.json"
    assert cli("check_scope.py", "examples/clear/../clear/scope.json", "--json").returncode == 2
    output = tmp_path / ".." / "escape.md"
    assert cli("render_draft.py", source, "--output", output).returncode == 2
    assert not (tmp_path.parent / "escape.md").exists()


def test_renderer_does_not_overwrite_hardlinked_input(tmp_path, scope):
    source = tmp_path / "scope.json"
    source.write_text(json.dumps(scope))
    output = tmp_path / "alias.md"
    output.hardlink_to(source)
    before = source.read_bytes()
    assert cli("render_draft.py", source, "--output", output, "--overwrite").returncode == 2
    assert source.read_bytes() == before
