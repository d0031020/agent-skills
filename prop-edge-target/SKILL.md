---
name: prop-edge-target
description: Back-calculate the net edge per trade (as edge divided by per-trade volatility) a strategy needs before it can pass a prop-firm style evaluation with a decent probability, by simulating the account rules on a shifted return shape. Use before or during research to turn "is this good enough?" into a number.
---

# Edge target from prop-account rules

Derive the minimum per-trade edge needed to pass a funded-trader evaluation and survive after it, so ideas can be judged against a number set in advance.

Provenance: Field-tested in a multi-agent coding workflow. Recompute all figures for your own account rules and strategy inputs.

## Steps
1. **Collect the account rules** from the firm's current official terms and record the date: account size, profit target, drawdown amount, drawdown type (**intraday trailing** vs end-of-day trailing vs static), when the trail locks, time limit (or none), daily loss limit, consistency rule, payout rules, fees and reset fees.
2. **Pick a return shape:** a real strategy's per-trade residuals together with each trade's worst intra-trade excursion (MAE) and best (MFE) and its trades per day. Shift the mean to a candidate edge E (points net of costs). Add a "half volatility" variant to see how volatility, not just edge, matters.
3. **Simulate:** block-bootstrap by trading-day blocks (for example 5 sessions) for a few thousand paths. For intraday trailing drawdown, apply MFE first then MAE inside each trade (conservative). Include costs in MAE.
4. **Choose position size** per scenario (best of a range of contract counts by expected value), but judge robustness separately from EV.
5. **Robust means:** pass probability above a threshold (for example 50%) **and** funded-phase survival over several months above a threshold (for example 70%). EV alone is misleading: with capped downside (the fee) a zero-edge strategy can show positive EV from lucky tails while almost never surviving.
6. **Sweep E** and report the smallest E meeting the robust definition for each drawdown type and for time-limited vs no-limit evaluations.
7. **Convert to edge/sigma** (E divided by per-trade SD) and a rule of thumb, then rescale: more trades per day lowers the per-trade need roughly with the square root of trades per day.
8. **Set the research gate from this number** before testing ideas, and compare candidates' edge/sigma against it. Also run the simulation on a matched random-entry baseline; a pass rate alone is not evidence of skill.

## Reading the output
- Time limits and intraday trailing drawdowns demand much larger edge/sigma than no-limit or static rules.
- If a detectable short-horizon edge is needed anyway, check the needed edge against the statistical power or minimum detectable effect of your own signal-testing method.

## Pitfalls
- Ignoring payout caps, consistency rules or fee resets makes EV optimistic; say so in the report.
- Bootstrapping individual trades instead of day blocks understates clustering.
- Using end-of-day trailing rules when the firm trails intraday understates failure.
- Rules change; re-read the firm's terms before relying on an old table.

## Risks
Simulation, not a promise. Prop firms' automation and copy rules vary; follow their terms. Not financial or investment advice.
