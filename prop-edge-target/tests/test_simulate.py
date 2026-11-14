from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np


def _load_sim_module():
    root = Path(__file__).resolve().parents[1]
    mod_path = root / "examples" / "simulate_edge_target.py"
    spec = importlib.util.spec_from_file_location("simulate_edge_target", mod_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sim = _load_sim_module()


def _base_args(**kwargs):
    data = {
        "account_json": None,
        "drawdown_type": "intraday_trailing",
        "trades_per_day": 5,
        "synthetic_days": 120,
        "synthetic_sigma": 120.0,
        "half_volatility": False,
        "block_len": 5,
        "paths": 500,
        "seed": 41,
        "edge_min": 0.0,
        "edge_max": 40.0,
        "edge_step": 20.0,
        "min_pass_prob": 0.5,
        "min_survival": 0.7,
        "funded_months": 4,
        "trading_days_per_month": 21,
        "eval_days_no_limit": 50,
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_pass_probability_is_non_decreasing_in_edge_with_tolerance():
    args = _base_args()
    result = sim.run_sweep(args)
    pass_probs = [row["pass_prob"] for row in result["rows"]]
    diffs = np.diff(pass_probs)
    assert np.all(diffs >= -0.03), pass_probs


def test_intraday_trailing_never_easier_than_static_for_same_edge():
    shape = sim.generate_synthetic_trade_shape(days=120, trades_per_day=5, seed=7, sigma=120.0)
    rules_intraday = sim.AccountRules(drawdown_type="intraday_trailing", time_limit_days=30)
    rules_static = sim.AccountRules(drawdown_type="static", time_limit_days=30)
    metrics_intraday = sim.run_monte_carlo(
        shape=shape,
        rules=rules_intraday,
        edge=30.0,
        n_paths=500,
        block_len=5,
        eval_days=30,
        funded_months=4,
        trading_days_per_month=21,
        seed=123,
    )
    metrics_static = sim.run_monte_carlo(
        shape=shape,
        rules=rules_static,
        edge=30.0,
        n_paths=500,
        block_len=5,
        eval_days=30,
        funded_months=4,
        trading_days_per_month=21,
        seed=123,
    )
    assert metrics_intraday["pass_prob"] <= metrics_static["pass_prob"] + 1e-12


def test_zero_edge_low_pass_and_survival_even_if_ev_positive():
    # Illustrative high-volatility, low-fee scenario, not typical account terms.
    shape = sim.generate_synthetic_trade_shape(days=150, trades_per_day=6, seed=99, sigma=300.0)
    # Remove finite-sample drift so the source returns really have zero mean.
    shape["residual"] -= shape["residual"].mean()
    rules = sim.AccountRules(
        profit_target=4500.0,
        drawdown_amount=2200.0,
        drawdown_type="intraday_trailing",
        trail_lock=1400.0,
        daily_loss_limit=950.0,
        fee=25.0,
        payout_on_pass=9000.0,
        time_limit_days=25,
    )
    metrics = sim.run_monte_carlo(
        shape=shape,
        rules=rules,
        edge=0.0,
        n_paths=600,
        block_len=5,
        eval_days=25,
        funded_months=4,
        trading_days_per_month=21,
        seed=55,
    )
    assert metrics["pass_prob"] < 0.20
    assert metrics["funded_survival"] < 0.20
    assert metrics["ev"] > 0.0
    # Match the default sweep's pass and conditional-survival thresholds.
    robust = metrics["pass_prob"] >= 0.50 and metrics["funded_survival"] >= 0.70
    assert robust is False


def test_same_seed_same_results():
    args = _base_args(seed=123, paths=400, edge_max=20.0, edge_step=10.0)
    r1 = sim.run_sweep(args)
    r2 = sim.run_sweep(args)
    assert r1 == r2


def test_day_block_bootstrap_preserves_blocks():
    values = np.arange(12, dtype=float).reshape(12, 1)
    rng = np.random.default_rng(3)
    sampled, idx = sim.bootstrap_day_blocks(values, block_len=3, out_days=9, rng=rng, return_indices=True)
    assert sampled.shape == (9, 1)
    assert np.array_equal(sampled[:, 0], idx.astype(float))
    for start in range(0, 9, 3):
        block = idx[start : start + 3]
        assert np.array_equal(block, np.arange(block[0], block[0] + len(block)))
