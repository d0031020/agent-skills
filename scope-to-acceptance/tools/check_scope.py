"""Check local scope drafts using only the Python standard library."""

import argparse
import json
import re
from pathlib import Path


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "scope.schema.json"
EXIT_CODES = {"ready": 0, "needs_info": 1, "invalid": 2}
NUMBER = re.compile(r"\d+(?:[-/.,:]\d+)*")
COMMITMENTS = ("budget", "deadline", "hours", "rate", "access")
CONTEXT = {
    "budget": r"\b(?:budget|price|cost|fee)\b",
    "deadline": r"\b(?:deadline|due|date)\b",
    "hours": r"\b(?:hours?|effort)\b",
    "rate": r"\b(?:rate|billing|hourly|fixed fee)\b",
    "access": r"\b(?:access|permission|credentials?|authorization)\b",
}
SENSITIVE = re.compile(
    r"\b(?:budget|price|costs?|fees?|rates?|billing|hourly|hours?|deadline|dates?|"
    r"access|credentials?|passwords?|permissions?|authorized|authorization|"
    r"dollars?|euros?|USD|EUR|GBP)\b|[$€£]", re.I
)
UNCONFIRMED = re.compile(
    r"\b(?:unknown|unconfirmed|tentative|TBD|to confirm|estimate|estimated|"
    r"not (?:confirmed|agreed|approved|provided|supplied|available))\b", re.I
)


def unsupported_number(text, quotes):
    # Whole statements prevent recycling a budget number as an acceptance threshold.
    numbers = set(NUMBER.findall(text))
    return bool(numbers) and not any(text in quote and numbers <= set(NUMBER.findall(quote)) for quote in quotes)


def unsupported_claim(text, quotes):
    return bool(SENSITIVE.search(text)) and not any(text in quote for quote in quotes)


def prose_fields(scope):
    yield "scope.project_summary", scope["project_summary"]
    for group, field in (("requirements", "text"), ("deliverables", "text"), ("acceptance", "check")):
        for index, item in enumerate(scope[group]):
            yield f"scope.{group}[{index}].{field}", item[field]
    for index, item in enumerate(scope["out_of_scope"]):
        yield f"scope.out_of_scope[{index}]", item


def _reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def resolve_path(path):
    candidate = Path(path).expanduser()
    if ".." in candidate.parts:
        raise ValueError("Parent traversal components are not allowed in file paths")
    return candidate.resolve()


def load_scope(path):
    return json.loads(
        resolve_path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicates,
        parse_constant=_reject_constant,
    )


def _structural(value, rule, root, path="scope"):
    """Implement only the schema keywords used by the bundled schema."""
    if "$ref" in rule:
        rule = root["$defs"][rule["$ref"].rsplit("/", 1)[1]]
    if "anyOf" in rule:
        if any(not _structural(value, branch, root, path) for branch in rule["anyOf"]):
            return []
        return [f"{path}: expected null or an object with value and source_quote"]
    types = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str),
        "null": lambda x: x is None,
    }
    if "type" in rule and not types[rule["type"]](value):
        return [f"{path}: expected {rule['type']}"]
    errors = []
    if "enum" in rule and value not in rule["enum"]:
        errors.append(f"{path}: expected one of {', '.join(rule['enum'])}")
    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0) or not value.strip():
            errors.append(f"{path}: must not be blank")
        if "pattern" in rule and not re.search(rule["pattern"], value):
            errors.append(f"{path}: does not match the allowed format")
    if isinstance(value, list):
        if len(value) < rule.get("minItems", 0):
            errors.append(f"{path}: needs at least {rule['minItems']} item(s)")
        if rule.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            errors.append(f"{path}: duplicate items")
        for index, item in enumerate(value):
            errors.extend(_structural(item, rule.get("items", {}), root, f"{path}[{index}]"))
    if isinstance(value, dict):
        properties = rule.get("properties", {})
        for key in rule.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required")
        for key, item in value.items():
            if key not in properties:
                if rule.get("additionalProperties") is False:
                    errors.append(f"{path}.{key}: unknown field")
            else:
                errors.extend(_structural(item, properties[key], root, f"{path}.{key}"))
    return errors


def quoted_sources(scope):
    """Trust numeric tokens only in quotes actually present in the embedded brief."""
    brief = scope["brief"]
    candidates = [r["source_quote"] for r in scope["requirements"]]
    candidates += [scope[key].get("source_quote", "") for key in COMMITMENTS
                   if isinstance(scope.get(key), dict)]
    return [quote for quote in candidates if isinstance(quote, str) and quote.strip() and quote in brief]


def strings(value, path="scope"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from strings(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, f"{path}.{key}")


def check_scope(scope):
    issues = []
    pending = []

    def issue(code, message, severity="needs_info"):
        issues.append({"code": code, "severity": severity, "message": message})
        if severity == "needs_info":
            pending.append(message)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for error in _structural(scope, schema, schema):
        issue("structure", error, "invalid")
    # Emit an explicit invention warning even when missing evidence breaks the schema.
    if isinstance(scope, dict):
        for key in COMMITMENTS:
            item = scope.get(key)
            if isinstance(item, dict) and not str(item.get("source_quote") or "").strip():
                issue("possibly_invented", f"{key}: possibly invented value; source quote is missing", "invalid")
    if issues:
        return {"status": "invalid", "issues": issues, "to_confirm": pending}

    for group in ("requirements", "deliverables", "acceptance"):
        ids = [item["id"] for item in scope[group]]
        if len(ids) != len(set(ids)):
            issue("duplicate_id", f"{group}: duplicate ids", "invalid")

    requirements = {item["id"] for item in scope["requirements"]}
    deliverables = {item["id"] for item in scope["deliverables"]}
    covered, accepted, placed = set(), set(), set()
    for item in scope["requirements"]:
        if item["source_quote"] not in scope["brief"]:
            issue("quote_mismatch", f"Requirement {item['id']}: source quote is absent from the brief", "invalid")
    for item in scope["deliverables"]:
        covered.update(item["covers"])
        if not item["covers"]:
            issue("deliverable_without_requirement", f"Deliverable {item['id']}: covers no requirement")
        for ref in item["covers"]:
            if ref not in requirements:
                issue("dangling_id", f"Deliverable {item['id']}: unknown requirement {ref}", "invalid")
    for item in scope["acceptance"]:
        ref = item["requirement_id"]
        accepted.add(ref)
        if ref not in requirements:
            issue("dangling_id", f"Acceptance {item['id']}: unknown requirement {ref}", "invalid")
    for kind in ("discovery", "implementation"):
        milestones = [m for m in scope["milestones"] if m["kind"] == kind]
        if len(milestones) > 1:
            issue("duplicate_milestone", f"{kind}: define a separate, single milestone", "invalid")
        if not milestones or not milestones[0]["deliverable_ids"]:
            issue(f"{kind}_missing", f"{kind}: milestone is missing or empty")
    for milestone in scope["milestones"]:
        placed.update(milestone["deliverable_ids"])
        for ref in milestone["deliverable_ids"]:
            if ref not in deliverables:
                issue("dangling_id", f"{milestone['kind']}: unknown deliverable {ref}", "invalid")
    for ref in sorted(requirements - covered):
        issue("requirement_without_deliverable", f"Requirement {ref}: no deliverable")
    for ref in sorted(requirements - accepted):
        issue("requirement_without_acceptance", f"Requirement {ref}: no acceptance check")
    for ref in sorted(deliverables - placed):
        issue("deliverable_without_milestone", f"Deliverable {ref}: not placed in a milestone")
    for ref in sorted(deliverables):
        kinds = {m["kind"] for m in scope["milestones"] if ref in m["deliverable_ids"]}
        if len(kinds) > 1:
            issue("milestone_overlap", f"Deliverable {ref}: split discovery and implementation outputs")

    for key in COMMITMENTS:
        item = scope.get(key)
        if item is None:
            issue("unconfirmed", f"{key}: to confirm")
        elif (item["source_quote"] not in scope["brief"] or item["value"] not in item["source_quote"]
              or not re.search(CONTEXT[key], item["source_quote"], re.I)
              or unsupported_number(item["value"], [item["source_quote"]])):
            issue("possibly_invented", f"{key}: possibly invented value; value must appear in a quote from the brief", "invalid")
        elif UNCONFIRMED.search(item["source_quote"]):
            issue("unconfirmed_value", f"{key}: quote describes an unconfirmed value; set the field to null and add a question", "invalid")

    quotes = quoted_sources(scope)
    for path, value in strings({key: value for key, value in scope.items() if key != "brief"}):
        if unsupported_number(value, quotes):
            issue("unsupported_number", f"{path}: full numeric statement lacks quoted support; possibly invented")
    for path, value in prose_fields(scope):
        if unsupported_claim(value, quotes):
            issue("unsupported_claim", f"{path}: commercial or access statement lacks quoted support; to confirm")

    def normalize(text):
        return " ".join(text.casefold().split()).rstrip(".")

    included = {normalize(r["text"]) for r in scope["requirements"]}
    for exclusion in scope["out_of_scope"]:
        if normalize(exclusion) in included:
            issue("scope_conflict", "Conflict: the same item is both required and out of scope")
    for assumption in scope["assumptions"]:
        issue("assumption", f"Assumption to confirm: {assumption}")
    for question in scope["to_confirm"]:
        issue("open_question", question)

    status = "invalid" if any(i["severity"] == "invalid" for i in issues) else "needs_info" if issues else "ready"
    return {"status": status, "issues": issues, "to_confirm": list(dict.fromkeys(pending))}


def inspect_path(path):
    try:
        scope = load_scope(path)
        return scope, check_scope(scope)
    except (OSError, ValueError, RecursionError) as exc:
        return None, {"status": "invalid", "issues": [
            {"code": "input", "severity": "invalid", "message": f"Cannot read scope: {exc}"}
        ], "to_confirm": []}


def format_report(report):
    lines = [f"Status: {report['status']}"]
    lines.extend(f"- [{i['severity']}] {i['code']}: {i['message']}" for i in report["issues"])
    if not report["issues"]:
        lines.append("- No blocking issues. Ready for human review only.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    _, report = inspect_path(args.scope)
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.as_json else format_report(report))
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
