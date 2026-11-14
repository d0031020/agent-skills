# prop-edge-target

## What it is
`prop-edge-target` is a skill package plus a runnable synthetic simulator that estimates the minimum per-trade edge needed to satisfy prop-style evaluation constraints. It sweeps candidate edge `E`, applies day-block bootstrap, enforces drawdown and daily-loss rules, and reports pass probability, funded-phase survival, and EV.

All numbers in this package are synthetic, illustrative examples.

## Why
- Turn vague "is this edge good enough?" questions into a numeric gate.
- Separate robust passability from EV, since EV alone can mislead under capped downside.
- Compare drawdown-rule variants (`static`, `eod_trailing`, `intraday_trailing`) under one reproducible framework.
- Evaluate a half-volatility scenario without changing account rules.

Not financial or investment advice.

## Install
Requires Python 3.12+. Create an environment from the pinned dependencies:

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

Verified 2026-11-14 in a fresh environment: `python -m pytest -q` gives 5 passed.

## Usage
Run the simulator (synthetic data only):

```bash
./.venv/bin/python examples/simulate_edge_target.py --pretty --seed 11 --paths 1200 --drawdown-type intraday_trailing
```

Optional half-volatility variant:

```bash
./.venv/bin/python examples/simulate_edge_target.py --pretty --seed 11 --paths 1200 --drawdown-type intraday_trailing --half-volatility
```

Expected output format:
- A one-line caution that output is synthetic and illustrative.
- A summary with `sigma`, `robust_edge`, and `robust_edge_sigma`.
- A CSV-like table for each swept edge.
- A JSON payload with the assumptions and all rows.

Actual output — **synthetic, illustrative** (the Usage command above uses the default simulation settings).

Runtime: about 10 s on an M1 Pro.

```text
Synthetic, illustrative output only. Not financial or investment advice.
sigma=121.0653 robust_edge=40.0 robust_edge_sigma=0.3304002380322898
edge,edge_sigma,pass_prob,funded_survival,ev
0.0000,0.000000,0.000000,0.000000,-150.000000
5.0000,0.041300,0.000000,0.000000,-150.000000
10.0000,0.082600,0.000000,0.000000,-150.000000
15.0000,0.123900,0.001667,0.000000,-145.000000
20.0000,0.165200,0.014167,0.000000,-107.500000
25.0000,0.206500,0.050833,0.245902,2.500000
30.0000,0.247800,0.132500,0.509434,247.500000
35.0000,0.289100,0.337500,0.822222,862.500000
40.0000,0.330400,0.553333,0.956325,1510.000000
45.0000,0.371700,0.761667,0.986871,2135.000000
50.0000,0.413000,0.893333,0.998134,2530.000000
55.0000,0.454300,0.973333,0.999144,2770.000000
60.0000,0.495600,0.990833,1.000000,2822.500000
65.0000,0.536900,0.998333,1.000000,2845.000000
70.0000,0.578200,1.000000,1.000000,2850.000000
75.0000,0.619500,1.000000,1.000000,2850.000000
80.0000,0.660800,1.000000,1.000000,2850.000000
```

The script also prints a JSON payload with the assumptions and all rows.

## How to verify
Run the full pytest suite:

```bash
./.venv/bin/python -m pytest -q
```

Actual result:

```text
.....                                                                    [100%]
5 passed in 0.75s
```

The zero-edge regression uses an explicitly illustrative scenario: per-trade volatility 300, fee 25, profit target 4500, and payout on pass 9000. The residual source is centered to zero mean. With the fixed seeds and 600 paths, EV is 215, pass probability is 2.67%, and conditional funded survival is 0%. It asserts positive EV and failure of the default robustness gate (50% pass probability and 70% conditional funded survival). This demonstrates that zero edge **can** show positive EV under the simplified payout model; it does not claim every zero-edge scenario does. The simulator is unchanged.

Reproduce the example output and runtime with default simulation settings:

```bash
time ./.venv/bin/python examples/simulate_edge_target.py --pretty --seed 11 --paths 1200 --drawdown-type intraday_trailing
```

## Known limitations
- The trade path model is synthetic and simplified; MAE/MFE dynamics are stylized.
- Intraday trailing is conservatively modeled as MFE then MAE per trade.
- EV model is intentionally simple (`-fee + payout_on_pass`), not a full payout-policy engine.
- Consistency rules, payout caps, and reset mechanics are not modeled.
- If `time_limit_days` is `null`, eval duration falls back to `--eval-days-no-limit`.

## License
MIT. See [LICENSE](LICENSE).

Drafted with AI assistance and reviewed by the author.
