"""Render a local scope as a draft; never submit or approve it."""

import argparse
from pathlib import Path

try:
    from .check_scope import (COMMITMENTS, EXIT_CODES, NUMBER, check_scope, inspect_path,
                             quoted_sources, resolve_path, unsupported_claim, unsupported_number)
except ImportError:
    from check_scope import (COMMITMENTS, EXIT_CODES, NUMBER, check_scope, inspect_path,
                            quoted_sources, resolve_path, unsupported_claim, unsupported_number)


def render(scope):
    report = check_scope(scope)
    if report["status"] == "invalid":
        raise ValueError("Refusing to render invalid scope")
    quotes = quoted_sources(scope)
    allowed = {token for quote in quotes for token in NUMBER.findall(quote)}

    def safe(value, pending=False):
        text = str(value)
        if not pending and unsupported_claim(text, quotes):
            text = "To confirm: unquoted commercial or access statement omitted."
        if unsupported_number(text, quotes):
            text = NUMBER.sub("[to confirm]", text)
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for char in "\\`*_{}[]()#!|":
            text = text.replace(char, "\\" + char)
        return " ".join(text.split())

    def bullets(values, pending=False):
        return [f"- {safe(value, pending)}" for value in values] or ["- None recorded."]

    def labeled(item, field="text"):
        return f"{safe(item['id'])}: {safe(item[field])}"

    lines = [
        "# Draft for review - not a quote or commitment", "",
        "DRAFT: Human review is required. This document submits no proposal and commits",
        "to no dates or prices. Confirm scope, permissions and commercial terms before use.", "",
        f"Checker status: {report['status']}", "",
        "## Project summary", "", safe(scope["project_summary"]), "",
        "## Milestones", "",
    ]
    deliverables = {d["id"]: d for d in scope["deliverables"]}
    requirements = {r["id"]: r for r in scope["requirements"]}
    for kind in ("discovery", "implementation"):
        lines += [f"### {kind.capitalize()} (proposed)", ""]
        selected = [m for m in scope["milestones"] if m["kind"] == kind]
        refs = selected[0]["deliverable_ids"] if selected else []
        lines += [f"- {labeled(deliverables[ref])}" for ref in refs] if refs else ["- To confirm: define milestone deliverables."]
        lines.append("")
    lines += ["## Scope", "", "### In scope (proposed)", ""]
    lines += [f"- {labeled(r)}" for r in scope["requirements"]]
    lines += ["", "### Out of scope (proposed)", ""] + bullets(scope["out_of_scope"])
    lines += ["", "### Assumptions (unconfirmed)", ""] + bullets(scope["assumptions"], pending=True)
    lines += ["", "## Acceptance table (proposed)", "",
              "| Requirement | Brief quote | Deliverables | Acceptance check | Method |",
              "| --- | --- | --- | --- | --- |"]
    for ref, requirement in requirements.items():
        outputs = "; ".join(labeled(d) for d in scope["deliverables"] if ref in d["covers"])
        checks = [a for a in scope["acceptance"] if a["requirement_id"] == ref] or [None]
        for check in checks:
            cells = [labeled(requirement), safe(requirement["source_quote"]), outputs or "To confirm",
                     labeled(check, "check") if check else "To confirm", check["method"] if check else "To confirm"]
            lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## Recorded terms (subject to human review)", ""]
    for key in COMMITMENTS:
        item = scope.get(key)
        lines.append(f"- {key.capitalize()}: {safe(item['value'])}; source: {safe(item['source_quote'])}" if item else f"- {key.capitalize()}: to confirm.")
    lines += ["", "## To confirm / missing information", ""] + bullets(report["to_confirm"], pending=True)
    lines += ["", "## Review risks", "",
              "Check the brief, evidence, conflicts and acceptance feasibility manually.",
              "Quoted text is not proof of authority or agreement. Protect confidential material;",
              "never include actual credentials. No proposal submission or external action occurs.", ""]
    draft = "\n".join(lines)
    if set(NUMBER.findall(draft)) - allowed:
        raise ValueError("Draft contains numeric content without quoted support")
    return draft


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", type=Path)
    parser.add_argument("--output", type=Path, default=Path("DRAFT.md"))
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output file")
    args = parser.parse_args(argv)
    scope, report = inspect_path(args.scope)
    if report["status"] == "invalid":
        print("Refusing to render invalid scope. Run check_scope.py for the issue list.")
        return 2
    try:
        output = resolve_path(args.output)
        source = resolve_path(args.scope)
        if output == source or (output.exists() and output.samefile(source)):
            raise ValueError("Output must be distinct from the input")
        draft = render(scope)
        with output.open("w" if args.overwrite else "x", encoding="utf-8") as handle:
            handle.write(draft)
    except (OSError, ValueError) as exc:
        print(f"Cannot write draft: {exc}")
        return 2
    print(f"Rendered DRAFT ({report['status']}). Human review required.")
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
