#!/usr/bin/env python3
"""Reconcile local write claims against independently obtained read evidence."""

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


MASK = "[REDACTED]"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
STATUSES = ("verified", "mismatch", "missing", "wrong_id", "stale", "pending")


class InvalidInput(ValueError):
    """An input cannot safely support reconciliation."""


def require(condition, message):
    if not condition:
        raise InvalidInput(message)


def timestamp(value):
    require(isinstance(value, str) and UTC.fullmatch(value),
            "Timestamps must be ISO-8601 UTC with Z and at most six fractional digits.")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise InvalidInput("Invalid calendar timestamp.") from None


def utc_text(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def object_keys(value, required, optional=()):
    require(isinstance(value, dict), "Expected a JSON object.")
    require(set(required) <= value.keys() <= set(required) | set(optional),
            "Missing or unknown structural keys.")


def fields(value, nonempty=False):
    require(isinstance(value, dict) and (value or not nonempty),
            "Fields must be an object; required_fields must not be empty.")
    for key, item in value.items():
        require(isinstance(key, str) and FIELD.fullmatch(key), "Invalid field name.")
        require(item is None or type(item) in (str, int, float, bool),
                "Field values must be JSON scalars.")
        require(type(item) is not float or math.isfinite(item),
                "Field numbers must be finite.")


def identifier(value):
    require(isinstance(value, str) and ID.fullmatch(value), "Invalid record ID.")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON keys are invalid.")
        result[key] = value
    return result


def invalid_constant(_value):
    raise InvalidInput("Nonfinite JSON constants are invalid.")


def exact_float(value):
    result = float(value)
    # Reject precision loss rather than let distinct source values falsely match.
    require(math.isfinite(result) and Decimal(value) == Decimal(str(result)),
            "A decimal number exceeds supported round-trip precision.")
    return result


def load_json(path):
    require(".." not in Path(path).parts, "Parent traversal is not allowed.")
    try:
        return json.loads(Path(path).resolve().read_text(encoding="utf-8"),
                          object_pairs_hook=unique_pairs, parse_constant=invalid_constant,
                          parse_float=exact_float)
    except (OSError, ValueError, RecursionError) as error:
        if isinstance(error, InvalidInput):
            raise
        # Never echo a path, JSON fragment, or underlying exception containing data.
        raise InvalidInput("Cannot read valid UTF-8 JSON from an input file.") from None


def validate(expected, observed):
    object_keys(expected, ("writes",))
    require(isinstance(expected["writes"], list) and expected["writes"],
            "writes must be a nonempty array.")
    seen = set()
    for write in expected["writes"]:
        object_keys(write, ("id", "written_at", "required_fields"))
        identifier(write["id"])
        require(write["id"] not in seen, "Duplicate expected IDs are invalid.")
        seen.add(write["id"])
        timestamp(write["written_at"])
        fields(write["required_fields"], nonempty=True)

    object_keys(observed, ("snapshot_at", "records"), ("pending_ids",))
    snapshot = timestamp(observed["snapshot_at"])
    records = observed["records"]
    require(records is None or isinstance(records, list), "records must be an array or null.")
    pending = observed.get("pending_ids", [])
    require(isinstance(pending, list), "pending_ids must be an array.")
    seen = set()
    for item in pending:
        identifier(item)
        require(item not in seen, "Duplicate pending IDs are invalid.")
        seen.add(item)
    require(records is not None or not pending,
            "Use records null alone for an unavailable snapshot.")
    for record in records or []:
        object_keys(record, ("id", "read_at", "fields"))
        identifier(record["id"])
        require(record["id"] not in seen, "Observed and pending IDs must be unique and disjoint.")
        seen.add(record["id"])
        require(timestamp(record["read_at"]) <= snapshot,
                "A record read cannot be later than snapshot_at.")
        fields(record["fields"])
    return snapshot


def equal(left, right):
    # JSON booleans and numbers are distinct, despite Python's True == 1.
    numeric = (int, float)
    if type(left) in numeric and type(right) in numeric:
        return Decimal(str(left)) == Decimal(str(right))
    return type(left) is type(right) and left == right


def differences(required, actual, shown):
    result = []
    for key in sorted(required):
        if key not in actual or not equal(required[key], actual[key]):
            item = {"field": key, "kind": "missing" if key not in actual else "value",
                    "expected": required[key] if key in shown else MASK}
            if key in actual:
                item["observed"] = actual[key] if key in shown else MASK
            result.append(item)
    return result


def masked(required, actual, shown):
    return {key: actual[key] if key in shown else MASK
            for key in sorted(required) if key in actual}


def stale_reasons(read_at, written_at, now, max_age):
    reasons = []
    if read_at < written_at:
        reasons.append("read_before_write")
    if (now - read_at).total_seconds() > max_age:
        reasons.append("max_age_exceeded")
    return reasons


def reconcile(expected, observed, max_age=300, show_fields=(), now=None):
    snapshot = validate(expected, observed)
    require(type(max_age) in (int, float) and math.isfinite(max_age) and max_age >= 0,
            "max-age must be a finite nonnegative number of seconds.")
    require(isinstance(show_fields, (tuple, list, set)) and
            all(isinstance(key, str) and FIELD.fullmatch(key) for key in show_fields),
            "show-fields must contain valid field names.")
    shown = set(show_fields)
    at = snapshot if now is None else timestamp(now)
    require(at >= snapshot, "now cannot be earlier than snapshot_at.")
    records = {item["id"]: item for item in observed["records"] or []}
    receipts = []
    for write in expected["writes"]:
        wanted = write["required_fields"]
        written = timestamp(write["written_at"])
        record = records.get(write["id"])
        actual = record["fields"] if record else {}
        item = {"id": write["id"], "written_at": utc_text(written),
                "status": "pending", "reasons": [], "differences": [],
                "expected_fields": masked(wanted, wanted, shown),
                "observed_fields": masked(wanted, actual, shown)}
        if observed["records"] is None or write["id"] in observed.get("pending_ids", []):
            item["reasons"] = ["readback_unavailable"]
        else:
            reasons = stale_reasons(snapshot, written, at, max_age)
            if record:
                item["read_at"] = utc_text(timestamp(record["read_at"]))
                reasons += stale_reasons(timestamp(record["read_at"]), written, at, max_age)
                item["differences"] = differences(wanted, actual, shown)
                item["status"] = ("stale" if reasons else
                                  "mismatch" if item["differences"] else "verified")
            elif reasons:
                item["status"] = "stale"
            else:
                candidates = [other for other in records.values()
                              if not differences(wanted, other["fields"], shown)]
                fresh = [other for other in candidates if not stale_reasons(
                    timestamp(other["read_at"]), written, at, max_age)]
                item["candidate_ids"] = sorted(other["id"] for other in fresh or candidates)
                if candidates and not fresh:
                    item["status"] = "stale"
                    reasons = ["matching_content_only_in_stale_records"]
                else:
                    item["status"] = "wrong_id" if fresh else "missing"
                    reasons = ["content_under_other_id" if fresh else "id_absent"]
            item["reasons"] = sorted(set(reasons))
        receipts.append(item)
    counts = {status: sum(item["status"] == status for item in receipts) for status in STATUSES}
    return {"status": "pass" if counts["verified"] == len(receipts) else "fail",
            "snapshot_at": utc_text(snapshot), "now": utc_text(at), "max_age_seconds": max_age,
            "show_fields": sorted(shown), "counts": counts, "receipts": receipts,
            "notice": "Consistency check, not an audit certification. Supplied evidence is not authenticated."}


def render_human(report):
    lines = [f"Receipt: {report['status']}"]
    if report["status"] == "invalid":
        return "\n".join(lines + report["errors"])
    lines += [f"Snapshot: {report['snapshot_at']} | Now: {report['now']}", report["notice"]]
    for item in report["receipts"]:
        lines.append(f"- {item['id']}: {item['status']}")
        if item["reasons"]:
            lines.append("  Reasons: " + ", ".join(item["reasons"]))
        if item.get("candidate_ids"):
            lines.append("  Candidate IDs: " + ", ".join(item["candidate_ids"]))
        for diff in item["differences"]:
            lines.append("  Difference: " + json.dumps(diff, sort_keys=True, ensure_ascii=True))
    return "\n".join(lines)


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise InvalidInput("Invalid command-line arguments; see --help.")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    json_only = "--json" in argv
    parser = Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--expected", required=True, help="Local expected JSON file")
    parser.add_argument("--observed", required=True, help="Local observed JSON file")
    parser.add_argument("--max-age", type=float, default=300, metavar="SECONDS")
    parser.add_argument("--show-fields", default="", metavar="FIELD,FIELD",
                        help="Allow values only for these required fields; default: mask all")
    parser.add_argument("--now", help="ISO-8601 UTC; default: observed snapshot_at")
    parser.add_argument("--json", action="store_true", help="Emit only JSON; default: text plus JSON")
    try:
        args = parser.parse_args(argv)
        shown = args.show_fields.split(",") if args.show_fields else []
        report = reconcile(load_json(args.expected), load_json(args.observed),
                           args.max_age, shown, args.now)
        exit_code = 0 if report["status"] == "pass" else 1
    except (InvalidInput, OverflowError, RecursionError):
        report = {"status": "invalid", "errors": ["Invalid input; check paths, schema, timestamps and options."]}
        exit_code = 2
    if not json_only:
        print(render_human(report))
        print("\nJSON receipt:")
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
