# Write read-back receipt

## What it is

An Agent Skill plus a Python tool that compares claimed external writes with
independent read-back evidence. It produces a receipt for each write:
`verified`, `mismatch`, `missing`, `wrong_id`, `stale`, or `pending`. Overall
`pass` requires **every write to be verified**. Missing evidence never passes.

Start with [SKILL.md](SKILL.md). The MVP reads local JSON fixtures and calls no
services. It uses only the Python standard library at runtime.

## Why

A write response can claim success even when nothing persisted. Independently
read the saved records, then compare their IDs, required values, and freshness
with the claim. This receipt is a **consistency check, not an audit
certification**. It cannot authenticate the files or prove the read path was
independent.

Regression tests for agent answers and receipts for agent side effects are
complementary: one checks answer behavior, the other checks evidence of a state
change. Neither establishes the other's correctness.

This is a new skill tested with synthetic local fixtures. All example names,
IDs, dates, values, and timing limits are fictional and illustrative. They do
not represent service guarantees or client deployments.

## Install

Copy this entire folder into your agent's documented skills directory, keeping
`SKILL.md`, `tools/`, `schema/`, and `examples/` together. Run the tool directly
with Python; no runtime dependency installation or network access is needed.

Tests require pytest, pinned in [requirements.txt](requirements.txt):

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

Verified 2026-11-14 in a fresh environment with Python 3.15.2: `python -m pytest -q` gives 116 passed. Other Python versions were not tested.

## Usage

1. Record claims in `expected.json` following
   [expected.schema.json](schema/expected.schema.json):

   ```json
   {
     "writes": [{
       "id": "crm-acme",
       "written_at": "2030-01-01T10:00:00Z",
       "required_fields": {"company": "Acme Example", "status": "active"}
     }]
   }
   ```

2. Obtain an independent read-back and supply `observed.json` following
   [observed.schema.json](schema/observed.schema.json):

   ```json
   {
     "snapshot_at": "2030-01-01T10:01:00Z",
     "records": [{
       "id": "crm-acme",
       "read_at": "2030-01-01T10:01:00Z",
       "fields": {"company": "Acme Example", "status": "active"}
     }]
   }
   ```

   Never use the write call's own response as the independent read-back. Record
   how the read was obtained in the handoff. Use `records: null` if unavailable;
   the mandatory `snapshot_at` then denotes the evidence manifest's as-of time.
   Use `records: []` only when a completed read found no records. For partial
   reads, list unresolved claimed IDs in optional `pending_ids`; those IDs must
   be unique and disjoint from records. Omitting an unresolved ID treats it as
   absent. Use one system and record namespace per file pair.

3. Run from the package directory:

   ```sh
   ./.venv/bin/python tools/readback_receipt.py \
     --expected examples/all-verified-crm/expected.json \
     --observed examples/all-verified-crm/observed.json
   ```

   The default emits a human-readable receipt followed by JSON on stdout.
   Add `--json` to emit only JSON, suitable for redirection to a new receipt file.
   Each example includes the generated `receipt.txt` and `receipt.json`.

| Option | Meaning |
| --- | --- |
| `--expected FILE` | Required local write-claim JSON. |
| `--observed FILE` | Required local read-back JSON, including an explicit unavailable state. |
| `--max-age SECONDS` | Nonnegative finite seconds; default `300`. The exact age boundary is accepted. |
| `--now UTC` | Evaluation time, default `snapshot_at`; must not precede it. No wall clock is read. |
| `--show-fields company,status` | Allow values only for these required fields. Default: mask every value. |
| `--json` | Emit JSON only. |

All unrelated field values are omitted, even if allow-listed. Required values
are `[REDACTED]` unless allow-listed, including in difference reports. Required
field names, IDs, candidate IDs, and timestamps remain visible. The allow-list
controls display only; every required field is still compared.

Accept only nonempty claim lists and required-field objects, unique IDs, and
scalar JSON field values (string, number, boolean, null). Match strings exactly;
distinguish booleans from numbers and omitted fields from null. Numbers compare
by decimal value, so `1` equals `1.0`. Reject decimal literals that would change
value during float round-trip parsing instead of silently rounding them.
Nested values, duplicate JSON keys, nonfinite numbers, unknown structural keys,
and parent traversal in input paths are invalid. Paths are resolved absolutely
inside the tool; it reads only the two supplied paths and writes no files.

Use timestamps in `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` form, with zero to six
fractional digits. Numeric UTC offsets and leap seconds are unsupported.
Each `read_at` must be at or before `snapshot_at`. A read predating its write or
older than `--max-age`, relative to `--now`, is stale. With the default `--now`,
freshness describes the snapshot's time, not the time you run the command.
Use an explicit evaluation time when reviewing an old snapshot today.

Apply statuses in this order:

- Unavailable evidence or an explicit pending ID yields `pending`.
- A stale snapshot yields `stale`, including for absent IDs.
- An existing claimed ID yields `stale` for an old record, otherwise `mismatch`
  for differences, otherwise `verified`. Stale records retain differences.
- For an absent claimed ID, match **all** required fields against other records.
  Fresh candidates yield `wrong_id` with sorted candidate IDs. Only stale
  matches yield `stale`; no match yields `missing`.

| Overall status | Exit | Meaning |
| --- | --- | --- |
| `pass` | `0` | Every claimed write is verified against the supplied evidence. |
| `fail` | `1` | At least one write remains non-verified. |
| `invalid` | `2` | Input or command-line options cannot support reconciliation. |

Act on non-verified items by correcting claims or obtaining new independent
evidence. Do not blindly repeat a write: retries can create duplicates. Obtain
authorization before external corrections. Attach the receipt, sanitized
inputs, command/options, and read method to the task result.

## How to verify/test

The following commands were run from this directory on 2026-11-14 using Python
`3.15.2` and pytest `9.2.0`. Results reflect the final code verification.

| Command | Observed result |
| --- | --- |
| `./.venv/bin/python --version` | `Python 3.15.2`; exit `0`. |
| `./.venv/bin/python -m pytest --version` | `pytest 9.2.0`; exit `0`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -o cache_dir=tests/.cache` | `116 passed in 3.22s`; exit `0`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/readback_receipt.py --expected examples/all-verified-crm/expected.json --observed examples/all-verified-crm/observed.json` | `pass`; `verified`; exit `0`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/readback_receipt.py --expected examples/fake-success/expected.json --observed examples/fake-success/observed.json` | `fail`; `missing`; exit `1`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/readback_receipt.py --expected examples/wrong-id/expected.json --observed examples/wrong-id/observed.json` | `fail`; `wrong_id`; exit `1`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/readback_receipt.py --expected examples/field-mismatch/expected.json --observed examples/field-mismatch/observed.json` | `fail`; `mismatch`; exit `1`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/readback_receipt.py --expected examples/stale-readback/expected.json --observed examples/stale-readback/observed.json` | `fail`; `stale`; exit `1`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/readback_receipt.py --expected examples/pending-readback/expected.json --observed examples/pending-readback/observed.json` | `fail`; `pending`; exit `1`. |
| `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python tools/readback_receipt.py --expected examples/mixed/expected.json --observed examples/mixed/observed.json` | `fail`; one of each of the six statuses; exit `1`. |

The six example exits of `1` are deliberate. Tests run every fixture in text
and JSON modes, check saved output byte for byte, and exercise each status,
the overall rule, masking in both output modes, allow-list boundaries,
determinism, stale precedence, time boundaries, null versus absent values,
numeric precision refusal, malformed JSON/UTF-8, invalid options, and exit `2`.
Pytest scratch data stays under `tests/`; omit scratch and `.venv/` from
distribution. These tests execute no services and make no real writes.

## Known limitations

- Supplied files and timestamps can be fabricated. Independently collect reads
  through an authorized path; the tool cannot establish authenticity, read
  completeness, cache behavior, permissions, atomic snapshots, or later changes.
  Record the actual read time, not merely the export or last-modified time.
- `wrong_id` is a content match, not proof that a candidate is the intended
  record. Generic required values can produce several candidates. Choose
  meaningful fields and investigate every candidate before changing anything.
- Use scalar fields in one namespace. Nested documents, array values, fuzzy
  matches, deletions, ID reuse, and transactional consistency are outside the MVP.
  Unsupported decimal precision is rejected; use canonical strings for values
  whose exact representation exceeds the accepted numeric range/precision.
- Masking is not a general personal-data or secret detector. Inputs remain
  unmasked on disk; visible IDs, field names, times, and allowed values may
  contain sensitive information. Sanitize metadata and review before sharing.
- Real CRM/calendar integrations, end-to-end agent discovery, and other Python
  versions were not exercised. No independent JSON Schema validation engine was
  run; the tool enforces its documented contract directly.

## License

MIT. See [LICENSE](LICENSE).

Drafted with AI assistance and reviewed by the author.
