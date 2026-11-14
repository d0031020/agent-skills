# Scope to acceptance

## What it is

An Agent Skill for freelancers and agencies turning an AI-workflow or agent
brief into a reviewable scope. It produces separate discovery and implementation
milestone drafts, in/out boundaries, assumptions, an acceptance table, and a
missing-information report. Start with [SKILL.md](SKILL.md).

The local checker and Markdown renderer use only the Python standard library.
Every output is a **draft for human review**, never a quote or commitment.

## Why

Vague briefs hide missing acceptance criteria, permissions, and commercial
terms. Trace each requirement to a deliverable and an acceptance check before
making a commitment. Unknown budget, deadline, hours, rate, or access remain
**to confirm**. The tools never submit proposals or act on external services.

This is a new skill, verified using synthetic fixtures. All example names,
dates, amounts, and limits are fictional and illustrative; no client material
or actual credentials are included.

## Install

Copy this entire folder into your agent's documented skills directory, keeping
`SKILL.md`, `schema/`, `tools/`, and `examples/` together. No installation or
network access is needed to run the tools with Python. Python versions earlier
than the tested version have not been exercised.

The tools use only the Python standard library. Tests need pytest, pinned in `requirements.txt`:

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

Verified 2026-11-14 in a fresh environment with Python 3.15.2: `python -m pytest -q` gives 109 passed. Other Python versions were not tested.

## Usage

Read the brief and list unanswered questions first. Fill `scope.json` using
[the schema](schema/scope.schema.json); [the clear fixture](examples/clear/scope.json)
shows the complete shape. Embed the authorized, sanitized brief and confirmed
answers in `brief`. Require literal source quotes for requirements and recorded
commercial/access values. Preserve client placeholders and keep public examples
synthetic when the source contains names or NDA material.

Use `project_summary`, `requirements`, `deliverables`, `acceptance`, `milestones`,
`out_of_scope`, `assumptions`, and `to_confirm`. A deliverable's `covers` contains
requirement ids. Each acceptance row has a `requirement_id`, a `check`, and a
`method` of `test`, `demo`, or `review`. Each milestone has a `kind` and
`deliverable_ids`. Define separate, nonempty `discovery` and `implementation`
milestones. Prefer alphabetic ids to avoid unsourced numbers.

For `budget`, `deadline`, and `hours`, use `null` for unknowns; otherwise provide
`value` and `source_quote`, both strings. Optional `rate` and `access` use the
same form; omitted values still need confirmation. The quote must occur in the
embedded brief, contain the value, and mention the relevant term in English.
Explicitly sourced nonnumeric terms, such as fixed-fee billing, are supported.
Never store actual credentials. Any assumption or unresolved question blocks
`ready`. Questions in the checker report supplement `to_confirm` automatically.

Run `python3 tools/check_scope.py scope.json`, adding `--json` for a structured
report. Fix errors or retain open questions. Then run
`python3 tools/render_draft.py scope.json --output DRAFT.md`.
Use `--overwrite` only to intentionally replace an existing output.

| Status | Exit | Meaning |
| --- | --- | --- |
| `ready` | `0` | No blocking mechanical issues; human review remains required. |
| `needs_info` | `1` | Coverage, milestones, terms, assumptions, questions, or source support need attention. A pending draft may be rendered. |
| `invalid` | `2` | Malformed data, dangling/duplicate ids, or invalid quote evidence. Rendering is refused. |

The renderer preserves the disclaimer, separates the milestones, includes every
requirement in the acceptance table, and lists gaps. It redacts numeric
statements absent from recorded quotes and unquoted commercial/access assertions
in proposed scope text. Redactions are not resolutions: review them against the
brief. A pending renderer run writes a file but still exits `1`.

## How to verify/test

The following commands were run from this package directory using Python
`3.15.2` and pytest `9.2.0`. These are the final observed results.

| Command | Observed result |
| --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -o cache_dir=tests/.cache` | `109 passed in 4.16s`; exit `0`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/check_scope.py examples/clear/scope.json` | `Status: ready`; exit `0`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/check_scope.py examples/missing-budget-acceptance/scope.json` | `Status: needs_info`; missing acceptance and budget reported; exit `1`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/check_scope.py examples/contradictory-scope/scope.json` | `Status: needs_info`; explicit conflict reported; exit `1`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/check_scope.py examples/invented-number-trap/scope.json` | `Status: invalid`; budget flagged as possibly invented because its quote is missing; exit `2`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/render_draft.py examples/clear/scope.json --output examples/clear/DRAFT.md --overwrite` | `Rendered DRAFT (ready). Human review required.`; exit `0`. |

Inspect [the rendered clear draft](examples/clear/DRAFT.md). The tests exercise
every checker rule, all example statuses in human-readable and JSON CLI modes,
invalid-input refusal, pending drafts, preservation of existing files, quote
relevance, unsupported numeric statements, unquoted commercial/access assertions,
and the invariant that draft numbers come from recorded quotes. Pytest scratch
data stays under `tests/`; omit it from distribution.

The `needs_info` and `invalid` fixture exits above are deliberate. No proposed
project acceptance checks, client integration, proposal submission, or
end-to-end agent discovery session was performed.

## Known limitations

- The embedded brief is user-supplied evidence, not independent verification.
  A quote can be fabricated along with the brief. Substring and English context
  checks cannot prove semantic support, permission, authority, or agreement.
- Numeric statements must appear verbatim within a recorded quote; unsupported
  statements, including numeric ids, are conservatively redacted in pending
  drafts. Rephrased but legitimate thresholds may need a confirmed clarification
  quote. Numeric checks cover digit expressions, including dates and decimals;
  written-out quantities and arbitrary languages require manual review.
- Commercial/access checks use English keywords and may flag benign text or miss
  synonyms. Actual credentials must be excluded by the author; this is not a
  comprehensive secret scanner.
- Exact normalized in/out duplicates are detected. Paraphrased contradictions
  must be recorded explicitly in `to_confirm` by the agent or reviewer.
- The checker verifies nonempty checks and mappings, not testability, complete
  brief extraction, acceptance feasibility, or execution of acceptance checks.
  It supports only the keywords used by the bundled JSON Schema, not arbitrary
  user-supplied schemas.
- Client use, end-to-end agent discovery, legal review, and other Python
  versions have not been verified. Review commercial language before
  sharing; drafts can still be mistaken for commitments. Use only material you
  are authorized to process and review output for confidential information.

## License

MIT. See [LICENSE](LICENSE).

Drafted with AI assistance and reviewed by the author.
