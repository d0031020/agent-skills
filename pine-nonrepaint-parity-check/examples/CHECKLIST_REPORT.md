# Example checklist report

Apply the four sections of [SKILL.md](../SKILL.md) to [pass_example.pine](pass_example.pine) and [fail_example.pine](fail_example.pine). Line references below are to those files, respectively. PASS means only the source property stated in that cell was checked. It does not turn an adjacent unperformed manual check into a PASS. `N/A` identifies an absent feature with source evidence.

Both examples contain fictional, illustrative, untuned values. Not financial or investment advice. The failure fixture intentionally contains an obviously fake token; it contains no usable credential.

## 1. Non-repainting

| Checklist item | pass_example.pine | fail_example.pine |
| --- | --- | --- |
| Confirmed-bar state/order changes and tick calculation | PASS — gate L18; orders L20, L24; tick calculation false L5. | FAIL — tick calculation true L5; gate L19 and orders L21, L25 are present. |
| Swings/pivots used only at confirmation; drawings not backdated | PASS (N/A) — L16–25 use no swing/pivot or drawing calls. | FAIL — pivot L27 is plotted back in time at L28. |
| Completed HTF read with explicit lookahead handling | PASS — L16 has `close[1]` and `lookahead_off`; historical/realtime equivalence remains manual: not run. | FAIL — L17 uses `lookahead_on` without `[1]`. |
| No pivot plot at a negative offset | PASS (N/A) — the only plot at L25 is an HTF series; no pivots. | FAIL — L27–28 use a pivot and `offset=-2`. |
| Explicit exchange timezone for session logic | PASS — `syminfo.timezone` at L17; session constant L11. | PASS — `syminfo.timezone` at L18; session constant L12. |
| Bar Replay sample of about 20 signals | manual: not run — relevant signals/orders L16–24. | manual: not run — relevant signals/orders L17–25. |

## 2. Parity with the Python engine

| Checklist item | pass_example.pine | fail_example.pine |
| --- | --- | --- |
| Next-bar market-order processing | PASS — `process_orders_on_close=false` L5; entry L20. Engine timing equality: manual: not run. | FAIL — `process_orders_on_close=true` L6; entry L21. Engine comparison: manual: not run. |
| Absolute stops/targets and one-tick trade-through assumption | PASS — absolute prices L22–24, trade-through setting L7. Actual fills: manual: not run. | PASS — absolute prices L23–25, trade-through setting L8. Actual fills: manual: not run. |
| Per-contract, per-side commission and slippage match engine | PASS for explicit settings only — L6–7. Equality with an engine cost model: manual: not run. | PASS for explicit settings only — L7–8. Equality with an engine cost model: manual: not run. |
| Flatten time, blackout windows, session entry cap match specification | manual: not run — session filter L17–20 only; flattening, blackout windows, and session caps are not implemented. No comparison specification supplied. | manual: not run — session filter L18–21 only; flattening, blackout windows, and session caps are not implemented. No comparison specification supplied. |
| Const/bounded parameters match predeclared grid | PASS for constants — L9–13. No inputs. Comparison with a reference grid: manual: not run. | PASS for constants — L10–14; illustrative pivot literals L27–28. No inputs. Reference-grid comparison: manual: not run. |
| Compare entry times/sides on identical dates and contract; explain differences | manual: not run — entry/exit L20–24; no engine, dataset, or trade lists supplied. | manual: not run — entry/exit L21–25; no engine, dataset, or trade lists supplied. |

## 3. Compile hygiene

| Checklist item | pass_example.pine | fail_example.pine |
| --- | --- | --- |
| Short title at most 10 characters | PASS — `ToyHTF` at L4. Compiler enforcement: manual: not run. | FAIL — `ToyHTFTooLong` at L4 exceeds 10 characters. Compiler enforcement: manual: not run. |
| Script version string and version bump | PASS for version presence — Pine v6 L1 and `SCRIPT_VERSION` L9. Increment-history check: manual: not run (new fixture). | PASS for version presence — Pine v6 L1 and `SCRIPT_VERSION` L10. Increment-history check: manual: not run (new fixture). |
| Drawing limits when labels or lines are used | PASS (N/A) — no label/line drawing calls in L1–25; `plot` L25 does not require a label/line limit. | PASS (N/A) — no label/line drawing calls in L1–28; plots L26, L28 do not require these limits. |

## 4. Safety

| Checklist item | pass_example.pine | fail_example.pine |
| --- | --- | --- |
| No credential/URL/account data; placeholder-only alert | PASS — placeholder-only `alert_message` L20, L24; source reviewed L1–25 for sensitive text. Alert expansion/delivery: manual: not run. | FAIL — L21 contains `FAKE_TOKEN_DO_NOT_USE` instead of a placeholder; deliberately fake, as stated at L3. Exit placeholder L25 passes. Delivery: manual: not run. |
| No private strategy parameters or performance results in public examples | PASS — fictional/illustrative disclosure L2; constants L9–13; source review L1–25 found no performance results. | PASS — fictional/illustrative disclosure L2; constants L10–14 and pivot literals L27–28; source review L1–28 found no performance results. |

## Executed verification

| Command | Result |
| --- | --- |
| `./.venv/bin/python -m pytest -q` | 38 passed; exit 0. |
| `./.venv/bin/python tools/pine_lint.py examples/pass_example.pine` | 14 PASS, 0 FAIL; exit 0. |
| `./.venv/bin/python tools/pine_lint.py examples/fail_example.pine` | 8 PASS, 6 FAIL; expected exit 1. |
| `./.venv/bin/python -m pynescript parse-and-dump examples/pass_example.pine` | AST produced without parser diagnostics using pynescript 0.3.0; exit 0. |
| `./.venv/bin/python -m pynescript parse-and-dump examples/fail_example.pine` | AST produced without parser diagnostics using pynescript 0.3.0; exit 0. |

The six linter failures are `shorttitle` (L4), `tick_calculation` (L5), `order_timing` (L6), `htf_security` (L17), `alert_safety` (L21), and `pivot_backdating` (L28). Several checklist rows describe the same underlying violation, so table failures are not a separate linter count.

Neither file was compiled or executed in TradingView. Parsing does not validate types, API usage, compiler title constraints, or strategy behavior. Manual replay, trade-list parity, execution settings, alert delivery, and historical/realtime consistency remain unverified. The toy exit bracket is submitted only after a filled entry's bar is confirmed; the entry bar is unprotected. Follow the Pine Editor steps and limitations in [README.md](../README.md) before drawing any conclusions.
