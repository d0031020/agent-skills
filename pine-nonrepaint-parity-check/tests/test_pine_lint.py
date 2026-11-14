from pathlib import Path
import subprocess
import sys

import pytest

from tools.pine_lint import lint


ROOT = Path(__file__).resolve().parents[1]
PASS = (ROOT / "examples/pass_example.pine").read_text(encoding="utf-8")
FAIL = (ROOT / "examples/fail_example.pine").read_text(encoding="utf-8")


def result(source, rule):
    return next(item for item in lint(source) if item.rule == rule)


def test_pass_example_has_zero_failures():
    assert len(lint(PASS)) == 14
    assert all(item.passed for item in lint(PASS))


def test_fail_example_triggers_every_intended_violation():
    assert {item.rule for item in lint(FAIL) if not item.passed} == {
        "tick_calculation", "order_timing", "htf_security", "pivot_backdating",
        "shorttitle", "alert_safety",
    }


@pytest.mark.parametrize("gate", ["if true", "if not barstate.isconfirmed", "if barstate.isconfirmed or true"])
def test_confirmed_bars(gate):
    changed = PASS.replace("if barstate.isconfirmed", gate)
    assert not result(changed, "confirmed_bars").passed
    changed = PASS + '\nstrategy.close_all(alert_message="{{strategy.order.id}}")\n'
    assert not result(changed, "confirmed_bars").passed
    assert not result(PASS + '\nvar int counter = 0\ncounter := counter + 1\n', "confirmed_bars").passed


@pytest.mark.parametrize("setting", ["calc_on_every_tick=true", "unused=false"])
def test_tick_calculation(setting):
    assert not result(PASS.replace("calc_on_every_tick=false", setting), "tick_calculation").passed


def test_order_timing():
    assert not result(PASS.replace("process_orders_on_close=false", "process_orders_on_close=true"), "order_timing").passed


@pytest.mark.parametrize("expression,lookahead", [
    ("close", "barmerge.lookahead_off"),
    ("close[1]", "barmerge.lookahead_on"),
    ("close", "barmerge.lookahead_on"),
    ("close[1] + close", "barmerge.lookahead_off"),
])
def test_htf_security(expression, lookahead):
    extra = f'\nother = request.security(syminfo.tickerid, "1D", {expression}, lookahead={lookahead})\n'
    assert not result(PASS + extra, "htf_security").passed
    named = PASS.replace("HTF, close[1]", "timeframe=HTF, expression=close[1]")
    assert result(named, "htf_security").passed


def test_pivot_backdating():
    pivot = '\npivot = ta.pivotlow(low, 2, 2)\nplot(pivot, offset=-2)\n'
    assert not result(PASS + pivot, "pivot_backdating").passed
    assert result(PASS + pivot.replace("offset=-2", "offset=0"), "pivot_backdating").passed
    positional = '\npivot = ta.pivothigh(high, 2, 2)\nplot(pivot, "Pivot", color.red, 1, plot.style_line, false, 0, -2)\n'
    assert not result(PASS + positional, "pivot_backdating").passed


def test_session_timezone():
    assert not result(PASS.replace(", syminfo.timezone", ""), "session_timezone").passed
    assert result(PASS.replace("syminfo.timezone", '"America/New_York"'), "session_timezone").passed


@pytest.mark.parametrize("exit_args", ["profit=20, loss=10", "stop=stopPrice", "stop=na, limit=limitPrice",
                                       "stop=stopPrice, limit=limitPrice, trail_points=2"])
def test_absolute_exits(exit_args):
    assert not result(PASS.replace("stop=stopPrice, limit=limitPrice", exit_args), "absolute_exits").passed


def test_limit_fill_assumption():
    assert not result(PASS.replace("backtest_fill_limits_assumption=1", "backtest_fill_limits_assumption=0"), "limit_fill_assumption").passed


@pytest.mark.parametrize("old,new", [
    ("commission_type=strategy.commission.cash_per_contract", "commission_type=strategy.commission.percent"),
    ("commission_value=1.0", "commission_value=-1"),
    ("commission_value=1.0", "commission_value=1e999"),
    ("slippage=1", "slippage=1.5"),
    ("slippage=1,", ""),
])
def test_explicit_costs(old, new):
    assert not result(PASS.replace(old, new), "explicit_costs").passed


def test_bounded_parameters():
    assert not result(PASS + '\nsize = input.int(1)\n', "bounded_parameters").passed
    assert not result(PASS.replace("const int STOP_TICKS", "int STOP_TICKS"), "bounded_parameters").passed
    assert result(PASS + '\nsize = input.int(1, minval=1, maxval=3)\n', "bounded_parameters").passed
    assert result(PASS + '\nsize = input.int(1, options=[1, 2, 3])\n', "bounded_parameters").passed
    assert result(PASS + '\nshow = input.bool(false)\n', "bounded_parameters").passed
    assert not result(PASS + '\nsize = input.int(1, minval=3, maxval=1)\n', "bounded_parameters").passed
    assert not result(PASS + '\nsize = input.int(1, options=[na])\n', "bounded_parameters").passed


def test_shorttitle():
    assert not result(PASS.replace('shorttitle="ToyHTF"', 'shorttitle="ElevenChars"'), "shorttitle").passed
    assert result(PASS.replace('shorttitle="ToyHTF"', 'shorttitle="TenChars10"'), "shorttitle").passed


@pytest.mark.parametrize("old,new", [("//@version=6", "//@version=5"),
                                     ('SCRIPT_VERSION = "1.0.0"', 'SCRIPT_VERSION = ""')])
def test_script_version(old, new):
    assert not result(PASS.replace(old, new), "script_version").passed


@pytest.mark.parametrize("drawing,limit", [("label", "max_labels_count"), ("line", "max_lines_count")])
def test_drawing_limits(drawing, limit):
    changed = PASS + f'\n{drawing}.new(bar_index, close)\n'
    assert not result(changed, "drawing_limits").passed
    assert result(changed.replace("pyramiding=0", f"pyramiding=0, {limit}=50"), "drawing_limits").passed
    assert not result(changed.replace("pyramiding=0", f"pyramiding=0, {limit}=0"), "drawing_limits").passed


@pytest.mark.parametrize("message", ["FAKE_TOKEN_DO_NOT_USE", "https://example.invalid/hook", "prefix {{strategy.order.id}}"])
def test_alert_safety(message):
    assert not result(PASS.replace("{{strategy.order.id}}", message), "alert_safety").passed
    assert not result(PASS + '\nalert("FAKE_TOKEN_DO_NOT_USE")\n', "alert_safety").passed
    assert not result(PASS + '\n// token=FAKE_TOKEN_DO_NOT_USE\n', "alert_safety").passed
    assert not result(PASS + '\nalertcondition(true, "Demo", "nonplaceholder")\n', "alert_safety").passed
    assert not result(PASS.replace('limit=limitPrice,', 'limit=limitPrice, alert_profit="nonplaceholder",'), "alert_safety").passed


def test_comments_and_strings_cannot_satisfy_checks():
    source = PASS.replace("calc_on_every_tick=false,", "")
    source += '\n// calc_on_every_tick=false\nconst string NOTE = "calc_on_every_tick=false"\n'
    assert not result(source, "tick_calculation").passed
    source = PASS + '\n// request.security(x, "1D", close, lookahead=barmerge.lookahead_on)\n'
    source += 'const string NOTE = "strategy.close_all()"\n'
    assert all(item.passed for item in lint(source))


def test_failure_line_numbers():
    expected = {"tick_calculation": (5,), "order_timing": (6,), "htf_security": (17,),
                "pivot_backdating": (28,), "shorttitle": (4,), "alert_safety": (21,)}
    assert {item.rule: item.lines for item in lint(FAIL) if not item.passed} == expected


@pytest.mark.parametrize("filename,exit_code,summary", [
    ("pass_example.pine", 0, "14 PASS, 0 FAIL"),
    ("fail_example.pine", 1, "8 PASS, 6 FAIL"),
])
def test_cli(filename, exit_code, summary):
    process = subprocess.run([sys.executable, str(ROOT / "tools/pine_lint.py"),
                              str(ROOT / "examples" / filename)], capture_output=True, text=True)
    assert process.returncode == exit_code
    assert summary in process.stdout
    assert "Does not replace manual replay checks or trade-list parity" in process.stdout


def test_cli_rejects_missing_file():
    process = subprocess.run([sys.executable, str(ROOT / "tools/pine_lint.py"),
                              str(ROOT / "examples/missing.pine")], capture_output=True, text=True)
    assert process.returncode == 2
    assert "error:" in process.stderr
