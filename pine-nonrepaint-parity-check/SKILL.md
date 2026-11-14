---
name: pine-nonrepaint-parity-check
description: Checklist to run before pushing or reviewing a TradingView Pine strategy, covering non-repainting rules, parity with a Python backtest engine, compile hygiene and secret safety. Use when writing, editing or reviewing .pine files that must reproduce research results.
---

# Pine non-repaint and parity checklist

Review every item. Report PASS or FAIL with source line numbers and supporting evidence. Any FAIL blocks acceptance. Mark unperformed checks `manual: not run`; do not count them as PASS. Use `N/A` only with an explanation and relevant source lines.

Adapted from a checklist used to review a Pine port against a Python backtest engine. End-to-end results are UNVERIFIED for this distribution.

Run `python tools/pine_lint.py <file.pine>` for mechanical checks. Read [the example report](examples/CHECKLIST_REPORT.md) for the complete checklist. The checker covers a conservative source subset; it does not establish non-repainting behavior, compilation, replay stability, or trade-list parity.

## 1. Non-repainting

- [ ] Gate state changes with `barstate.isconfirmed`; set `calc_on_every_tick = false`.
- [ ] Use swings/pivots only at their **confirmation** bar, never back-date them. Place labels at the bar where the information became known; a dotted line may point back to the true bar.
- [ ] Set `request.security` to `lookahead = barmerge.lookahead_off` **and** accept the higher-timeframe value only once that bar is complete (its close time <= the current bar's close time), or read it with a `[1]` offset. Never use `lookahead_on` without `[1]`.
- [ ] Reject any `ta.pivothigh` / `ta.pivotlow` result plotted at a negative offset as if it were known earlier.
- [ ] Set an explicit exchange timezone (`syminfo.timezone` or the exchange's named timezone) for session times.
- [ ] Replay check (manual): step through bar replay, sample about 20 signals, and confirm none disappear after they appear.

## 2. Parity with the Python engine

- [ ] Set `process_orders_on_close = false` for next-bar market-order processing. Verify that the engine uses the same timing and available bars.
- [ ] Submit stops and targets as absolute prices via `strategy.exit(stop=, limit=)`. Set `backtest_fill_limits_assumption = 1` when the engine requires a 1-tick trade-through for limit fills.
- [ ] Set commission per contract per side and explicit slippage ticks. Manually verify that both equal the comparison engine's cost model.
- [ ] Match flatten time, blackout windows, and the per-session entry cap to the written specification.
- [ ] Declare fixed parameters as `const`; constrain inputs with finite options or explicit bounds. Manually verify the allowed values against the predeclared grid.
- [ ] Compare trade lists (entry time, side) on the same dates and contract. Explain every difference, including bar construction, contract roll, and missing data. Define acceptance criteria before comparison; parity remains UNVERIFIED until this check is performed.

## 3. Compile hygiene

- [ ] Keep `shorttitle` to 10 characters or fewer. UNVERIFIED: compiler enforcement of this limit must be checked in the current Pine Editor.
- [ ] Bump the script version string on each change.
- [ ] Set `max_labels_count` / `max_lines_count` when drawings are used.

## 4. Safety

- [ ] **Exclude webhook URLs, tokens, account IDs, and credentials from scripts and alert text.** Use a placeholder-only alert message; configure any real template privately in the TradingView UI. The deliberate failure fixture contains only an obviously fake token.
- [ ] Exclude private strategy parameters and performance results from public material. Use clearly labeled, fictional values in examples.

## Pitfalls

- Tester results do not prove signal stability; repainting can invalidate apparent results. Always perform the replay check.
- `lookahead_on` without completed-data handling can silently introduce future information.
- Tester settings (fill assumptions, commission, slippage) default to unrealistic values; set them explicitly.

Use [pass_example.pine](examples/pass_example.pine) for an illustrative mechanical-check fixture and [fail_example.pine](examples/fail_example.pine) to exercise deliberate failures. Neither example has verified replay behavior or backtest parity. A delayed HTF read with `lookahead_off` alone is not proof of historical/realtime equivalence.

## Risks and terms

Not financial or investment advice. The examples are educational fixtures with fictional, untuned values; they are not trading recommendations. Repainting, intrabar order paths, gaps, data differences, and unrealistic costs can invalidate backtests or cause losses. Static checks cannot establish profitability or safe execution. Re-verify Pine behavior and tester settings after platform updates, and check applicable broker and trading-program rules before any automation.
