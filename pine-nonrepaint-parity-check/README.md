# Pine non-repaint and parity check

## What it is

A review skill for TradingView Pine strategies, with four checklist sections, two Pine v6 fixtures, a small Python static checker, and pytest tests. Start with [SKILL.md](SKILL.md); see [the full example checklist report](examples/CHECKLIST_REPORT.md) for source line references and unperformed checks.

## Why

Repainting, order timing, and cost assumptions can invalidate a backtest comparison. Repeatable mechanical checks catch some source mistakes; replay and trade-list comparison supply evidence that source inspection cannot provide. All example values are fictional, illustrative, and untuned. No private strategy or performance results are included.

Not financial or investment advice.

## Install

Keep `SKILL.md`, `README.md`, `examples/`, `tools/`, and `tests/` together. The checker itself uses only the Python standard library; `requirements.txt` pins `pytest` (tests) and `pynescript` (optional syntax check). Use Python 3.10 or newer; verification used Python 3.15.2, other versions were not tested.

```sh
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Usage

Apply every item in `SKILL.md`. Report PASS or FAIL with source line numbers. Mark unperformed manual items `manual: not run`; any FAIL blocks acceptance, and pending manual items prevent an end-to-end verification claim.

```sh
./.venv/bin/python tools/pine_lint.py examples/pass_example.pine
./.venv/bin/python tools/pine_lint.py examples/fail_example.pine
```

The second command intentionally exits with status 1. Each deliberate source violation has a `// VIOLATION:` comment and a corresponding test. Run the checker on your own `.pine` file using the same command form. Exit codes are 0 for no mechanical failures, 1 for failures, and 2 for invalid CLI arguments or unreadable/invalid input files.

The fixtures compare close with the previous daily close. Use a chart timeframe below one day; a runtime guard rejects equal or higher timeframes. The session is explicitly evaluated in `syminfo.timezone`. Session, stop, target, commission, and slippage values exist only to demonstrate the checklist.

## How to verify/test

The following commands were run from this package directory:

| Command | Observed result |
| --- | --- |
| `./.venv/bin/python -m pytest -q` | `38 passed`; exit 0. Covers all 14 rules, both fixtures, CLI exit codes, line numbers, comment/string masking, and negative cases. |
| `./.venv/bin/python tools/pine_lint.py examples/pass_example.pine` | `Summary: 14 PASS, 0 FAIL. Manual checks: not run.`; exit 0. |
| `./.venv/bin/python tools/pine_lint.py examples/fail_example.pine` | `Summary: 8 PASS, 6 FAIL. Manual checks: not run.`; expected exit 1. |
| `./.venv/bin/python -m pynescript --version` | `pynescript, version 0.3.0`; exit 0. |
| `./.venv/bin/python -m pynescript parse-and-dump examples/pass_example.pine` | Produced an AST without parser diagnostics; exit 0. |
| `./.venv/bin/python -m pynescript parse-and-dump examples/fail_example.pine` | Produced an AST without parser diagnostics; exit 0. Deliberate semantic violations remain. |

`pynescript` is a third-party syntax parser, not the TradingView compiler. Both files were parsed; neither was compiled or run in TradingView. Syntax acceptance does not validate Pine types, API contracts, title limits, broker-emulator behavior, or alerts. No Python backtest engine or reference trade list is included or verified.

Complete these manual steps in TradingView:

1. Open the Pine Editor, paste `examples/pass_example.pine` into a new strategy, save, and use **Add to chart** on a timeframe below one day. Record any compiler diagnostics. Repeat in a separate editor script for the deliberate failure fixture; do not treat syntax-parser acceptance as compiler acceptance.
2. Inspect strategy properties for tick calculation, order processing, commission, slippage, and the limit-order trade-through assumption. Check exchange session timezone and actual order prices/timing.
3. On the pass fixture, step through Bar Replay, sample about 20 signals, then reload and compare. Record whether signals change or disappear. Do not infer realtime equivalence from this static fixture.
4. Compare exported entry times and sides with a separately supplied Python engine on identical dates, symbol/contract, session, data, and costs. Explain each difference, including gaps and contract rolls. Verify flattening, blackout windows, entry caps, and the parameter grid against a written specification.
5. Verify version increments against the prior source, review all text for sensitive information, and test placeholder behavior in the alert UI without credentials or live order routing.

All of those TradingView, replay, alert-delivery, and trade-list checks are **manual: not run** in this package preparation.

## Known limitations

- The checker is a conservative lexical checker for source shaped like these fixtures. It recognizes multiline calls and ignores comments/strings for code checks, but is not a complete Pine parser or type checker. Unsupported syntax can cause false positives or false negatives.
- Confirmation checks require a direct enclosing `if barstate.isconfirmed` or `if barstate.isconfirmed and ...` without `or`. Function-mediated guards and general control/data flow are not resolved. Computed series are allowed outside the gate; order calls and `:=` mutations are checked.
- HTF checks require `lookahead_off` and a direct `series[1]` expression. Tuple reads, aliases, and completed-time alternatives from the manual checklist need separate review. `close[1]` with `lookahead_off` is not proof of identical historical and realtime delivery.
- When a pivot call exists, the checker conservatively rejects negative or nonliteral offsets on `plot`, `plotshape`, `plotchar`, and `plotarrow`, even if the plotted series is unrelated. It cannot prove pivot confirmation or detect all backdating through drawings or indirect code.
- Explicit timezone presence is checked; whether a named zone matches the instrument's exchange is manual. Explicit `stop`/`limit` argument presence is checked; price units, tick rounding, and economic meaning are manual.
- Inputs must have literal options or bounds; fixed parameters are recognized by uppercase typed declarations. Lowercase, untyped, aliased, and computed parameters require manual review. Grid compliance and version increment history are manual.
- The fixtures use no labels or line drawings, so drawing-limit checks are not applicable to them. Tests exercise both `label.new` and `line.new` limits. Other drawing APIs need manual review.
- Alert checks require literal placeholder-only text and scan common credential markers, URLs, and the fake token. This is not a comprehensive secret detector. Actual placeholder expansion and delivery are unverified; configure and verify the UI template privately.
- The toy strategy submits its stop/target only after an entry has filled and the next bar is confirmed, leaving the entry bar unprotected. It has no session-end flatten, blackout windows, or per-session entry cap. It is not a production risk-control template.
- Gaps, intrabar execution paths, changing data, and unrealistic costs can cause substantial losses and invalidate comparisons. No profitability, execution safety, replay stability, or parity is established. Not financial or investment advice.

## License

MIT. See [LICENSE](LICENSE).

Drafted with AI assistance and reviewed by the author.
