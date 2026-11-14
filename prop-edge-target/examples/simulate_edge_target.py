#!/usr/bin/env python3
"""Synthetic prop-rule edge targeting simulator.

All defaults are synthetic and illustrative only.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


DRAW_TYPES = ("static", "eod_trailing", "intraday_trailing")


@dataclass(frozen=True)
class AccountRules:
    # Fictional, illustrative defaults only.
    profit_target: float = 3000.0
    drawdown_amount: float = 2500.0
    drawdown_type: str = "intraday_trailing"
    trail_lock: float = 1500.0
    daily_loss_limit: float = 1200.0
    fee: float = 150.0
    payout_on_pass: float = 3000.0
    time_limit_days: Optional[int] = 30

    def validate(self) -> None:
        if self.drawdown_type not in DRAW_TYPES:
            raise ValueError(f"drawdown_type must be one of {DRAW_TYPES}")
        if self.drawdown_amount <= 0:
            raise ValueError("drawdown_amount must be > 0")
        if self.daily_loss_limit <= 0:
            raise ValueError("daily_loss_limit must be > 0")
        if self.fee < 0:
            raise ValueError("fee must be >= 0")


def generate_synthetic_trade_shape(
    days: int,
    trades_per_day: int,
    seed: int,
    sigma: float = 120.0,
) -> Dict[str, np.ndarray]:
    """Generate synthetic residual, MAE, MFE arrays with deterministic seed."""
    rng = np.random.default_rng(seed)
    residual = rng.normal(loc=0.0, scale=sigma, size=(days, trades_per_day))

    mae = np.abs(rng.normal(loc=0.45 * sigma, scale=0.28 * sigma, size=(days, trades_per_day)))
    mfe = np.abs(rng.normal(loc=0.65 * sigma, scale=0.35 * sigma, size=(days, trades_per_day)))
    return {"residual": residual, "mae": mae, "mfe": mfe}


def bootstrap_day_blocks(
    values: np.ndarray,
    block_len: int,
    out_days: int,
    rng: np.random.Generator,
    return_indices: bool = False,
) -> np.ndarray | Tuple[np.ndarray, np.ndarray]:
    """Bootstrap day blocks. If return_indices, returns sampled day indices too."""
    if values.ndim != 2:
        raise ValueError("values must be 2D (days x trades)")
    if block_len <= 0:
        raise ValueError("block_len must be >= 1")
    n_days = values.shape[0]
    if n_days < block_len:
        raise ValueError("block_len cannot exceed source days")
    starts = rng.integers(0, n_days - block_len + 1, size=int(np.ceil(out_days / block_len)))
    idx = np.concatenate([np.arange(s, s + block_len) for s in starts])[:out_days]
    sampled = values[idx]
    if return_indices:
        return sampled, idx
    return sampled


def _floor(drawdown_type: str, drawdown_amount: float, trail_peak: float, lock_hit: bool) -> float:
    if drawdown_type == "static":
        return -drawdown_amount
    floor = trail_peak - drawdown_amount
    if lock_hit:
        floor = max(floor, 0.0)
    return floor


def simulate_eval_path(
    residual_days: np.ndarray,
    mae_days: np.ndarray,
    mfe_days: np.ndarray,
    edge: float,
    rules: AccountRules,
    enforce_profit_target: bool,
) -> Dict[str, Any]:
    equity = 0.0
    trail_peak = 0.0
    lock_hit = False
    day_count = residual_days.shape[0]
    trades_per_day = residual_days.shape[1]

    for day in range(day_count):
        day_start = equity
        day_min = equity
        day_close = equity

        for t in range(trades_per_day):
            r = edge + residual_days[day, t] - rules.fee / trades_per_day
            mae = mae_days[day, t]
            mfe = mfe_days[day, t]
            entry = day_close

            if rules.drawdown_type == "intraday_trailing":
                interim_high = entry + max(0.0, r + mfe)
                trail_peak = max(trail_peak, interim_high)
                lock_hit = lock_hit or (trail_peak >= rules.trail_lock)
                floor_now = _floor(rules.drawdown_type, rules.drawdown_amount, trail_peak, lock_hit)
                interim_low = interim_high - (mfe + mae)
                day_min = min(day_min, interim_low)
                if interim_low < floor_now:
                    return {"pass": False, "breach": True, "equity": interim_low}
            else:
                interim_low = entry - mae
                day_min = min(day_min, interim_low)

            day_close = entry + r

            if rules.drawdown_type == "intraday_trailing":
                trail_peak = max(trail_peak, day_close)
                lock_hit = lock_hit or (trail_peak >= rules.trail_lock)
                floor_now = _floor(rules.drawdown_type, rules.drawdown_amount, trail_peak, lock_hit)
                if day_close < floor_now:
                    return {"pass": False, "breach": True, "equity": day_close}

        equity = day_close

        if day_start - day_min > rules.daily_loss_limit:
            return {"pass": False, "breach": True, "equity": day_min}

        if rules.drawdown_type == "eod_trailing":
            trail_peak = max(trail_peak, equity)
            lock_hit = lock_hit or (trail_peak >= rules.trail_lock)

        floor_eod = _floor(rules.drawdown_type, rules.drawdown_amount, trail_peak, lock_hit)
        if equity < floor_eod:
            return {"pass": False, "breach": True, "equity": equity}

        if enforce_profit_target and equity >= rules.profit_target:
            return {"pass": True, "breach": False, "equity": equity}

    if enforce_profit_target:
        return {"pass": False, "breach": False, "equity": equity}
    return {"pass": True, "breach": False, "equity": equity}


def run_monte_carlo(
    shape: Dict[str, np.ndarray],
    rules: AccountRules,
    edge: float,
    n_paths: int,
    block_len: int,
    eval_days: int,
    funded_months: int,
    trading_days_per_month: int,
    seed: int,
) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    residual = shape["residual"]
    mae = shape["mae"]
    mfe = shape["mfe"]

    funded_days = funded_months * trading_days_per_month
    pass_count = 0
    funded_survive_count = 0
    funded_survive_given_pass = 0
    ev_values: List[float] = []

    for _ in range(n_paths):
        eval_resid = bootstrap_day_blocks(residual, block_len, eval_days, rng)
        eval_mae = bootstrap_day_blocks(mae, block_len, eval_days, rng)
        eval_mfe = bootstrap_day_blocks(mfe, block_len, eval_days, rng)
        eval_result = simulate_eval_path(eval_resid, eval_mae, eval_mfe, edge=edge, rules=rules, enforce_profit_target=True)
        passed = bool(eval_result["pass"])
        pass_count += int(passed)
        ev_values.append(-rules.fee + (rules.payout_on_pass if passed else 0.0))

        if not passed:
            continue

        funded_resid = bootstrap_day_blocks(residual, block_len, funded_days, rng)
        funded_mae = bootstrap_day_blocks(mae, block_len, funded_days, rng)
        funded_mfe = bootstrap_day_blocks(mfe, block_len, funded_days, rng)
        funded_result = simulate_eval_path(
            funded_resid,
            funded_mae,
            funded_mfe,
            edge=edge,
            rules=rules,
            enforce_profit_target=False,
        )
        survived = bool(funded_result["pass"] and not funded_result["breach"])
        funded_survive_count += int(survived)
        funded_survive_given_pass += int(survived)

    pass_prob = pass_count / n_paths
    funded_survival_unconditional = funded_survive_count / n_paths
    funded_survival_conditional = funded_survive_given_pass / pass_count if pass_count else 0.0
    ev = float(np.mean(ev_values))
    return {
        "pass_prob": pass_prob,
        "funded_survival": funded_survival_conditional,
        "funded_survival_unconditional": funded_survival_unconditional,
        "ev": ev,
    }


def parse_account_rules(account_json: Optional[str], drawdown_type: Optional[str]) -> AccountRules:
    values = asdict(AccountRules())
    if account_json:
        with open(account_json, "r", encoding="utf-8") as f:
            incoming = json.load(f)
        values.update(incoming)
    if drawdown_type:
        values["drawdown_type"] = drawdown_type
    rules = AccountRules(**values)
    rules.validate()
    return rules


def run_sweep(args: argparse.Namespace) -> Dict[str, Any]:
    rules = parse_account_rules(args.account_json, args.drawdown_type)
    shape = generate_synthetic_trade_shape(
        days=args.synthetic_days,
        trades_per_day=args.trades_per_day,
        seed=args.seed,
        sigma=args.synthetic_sigma,
    )
    if args.half_volatility:
        shape = {k: v * 0.5 for k, v in shape.items()}

    e_values = np.arange(args.edge_min, args.edge_max + (args.edge_step / 2.0), args.edge_step)
    sigma = float(np.std(shape["residual"], ddof=1))
    rows: List[Dict[str, float]] = []

    robust_edge = None
    robust_row: Optional[Dict[str, float]] = None

    eval_days = rules.time_limit_days if rules.time_limit_days is not None else args.eval_days_no_limit

    for idx, edge in enumerate(e_values):
        metrics = run_monte_carlo(
            shape=shape,
            rules=rules,
            edge=float(edge),
            n_paths=args.paths,
            block_len=args.block_len,
            eval_days=eval_days,
            funded_months=args.funded_months,
            trading_days_per_month=args.trading_days_per_month,
            seed=args.seed + (idx * 1009),
        )
        row = {"edge": float(edge), "edge_sigma": float(edge / sigma), **metrics}
        rows.append(row)

        if robust_edge is None and row["pass_prob"] >= args.min_pass_prob and row["funded_survival"] >= args.min_survival:
            robust_edge = float(edge)
            robust_row = row

    return {
        "assumptions": {
            "synthetic_only": True,
            "illustrative_only": True,
            "half_volatility": bool(args.half_volatility),
            "seed": args.seed,
            "paths": args.paths,
            "block_len": args.block_len,
            "trades_per_day": args.trades_per_day,
            "eval_days": eval_days,
            "funded_months": args.funded_months,
            "account_rules": asdict(rules),
            "robust_thresholds": {"pass_prob": args.min_pass_prob, "funded_survival": args.min_survival},
        },
        "sigma": sigma,
        "robust_edge": robust_edge,
        "robust_edge_sigma": (robust_edge / sigma) if robust_edge is not None else None,
        "robust_row": robust_row,
        "rows": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synthetic edge target simulation (illustrative only).")
    parser.add_argument("--account-json", type=str, default=None, help="Path to account rules JSON (illustrative values only).")
    parser.add_argument("--drawdown-type", choices=DRAW_TYPES, default=None, help="Override drawdown type.")
    parser.add_argument("--trades-per-day", type=int, default=6)
    parser.add_argument("--synthetic-days", type=int, default=180)
    parser.add_argument("--synthetic-sigma", type=float, default=120.0)
    parser.add_argument("--half-volatility", action="store_true")
    parser.add_argument("--block-len", type=int, default=5)
    parser.add_argument("--paths", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--edge-min", type=float, default=0.0)
    parser.add_argument("--edge-max", type=float, default=80.0)
    parser.add_argument("--edge-step", type=float, default=5.0)
    parser.add_argument("--min-pass-prob", type=float, default=0.50)
    parser.add_argument("--min-survival", type=float, default=0.70)
    parser.add_argument("--funded-months", type=int, default=6)
    parser.add_argument("--trading-days-per-month", type=int, default=21)
    parser.add_argument("--eval-days-no-limit", type=int, default=60)
    parser.add_argument("--pretty", action="store_true", help="Print human-readable summary before JSON.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = run_sweep(args)

    if args.pretty:
        print("Synthetic, illustrative output only. Not financial or investment advice.")
        print(
            f"sigma={result['sigma']:.4f} robust_edge={result['robust_edge']} "
            f"robust_edge_sigma={result['robust_edge_sigma']}"
        )
        print("edge,edge_sigma,pass_prob,funded_survival,ev")
        for row in result["rows"]:
            print(
                f"{row['edge']:.4f},{row['edge_sigma']:.6f},{row['pass_prob']:.6f},"
                f"{row['funded_survival']:.6f},{row['ev']:.6f}"
            )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
