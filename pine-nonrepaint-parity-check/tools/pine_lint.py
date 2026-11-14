"""Conservative source checks for the example-style Pine subset; not a compiler."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import math
from pathlib import Path
import re


@dataclass(frozen=True)
class Result:
    rule: str
    passed: bool
    lines: tuple[int, ...]
    detail: str


@dataclass(frozen=True)
class Call:
    name: str
    start: int
    args: tuple[str, ...]

    def named(self, name: str) -> str | None:
        for arg in self.args:
            match = re.match(rf"^{re.escape(name)}\s*=\s*(.*)$", arg, re.S)
            if match:
                return match[1].strip()
        return None

    def value(self, name: str, position: int) -> str | None:
        named = self.named(name)
        positional = [arg for arg in self.args if not re.match(r"^\w+\s*=", arg)]
        return named if named is not None else (
            positional[position] if len(positional) > position else None
        )


TOKEN = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|//[^\n]*|/\*.*?\*/''', re.S)
CALL = re.compile(r"(?<![\w.])([A-Za-z_]\w*(?:\.\w+)*)\s*\(")


def masked(source: str, strings: bool = False) -> str:
    def replace(match: re.Match) -> str:
        if match[0].startswith(("//", "/*")) or strings:
            return re.sub(r"[^\n]", " ", match[0])
        return match[0]
    return TOKEN.sub(replace, source)


def calls(source: str) -> list[Call]:
    code, syntax = masked(source), masked(source, strings=True)
    found = []
    for match in CALL.finditer(syntax):
        depth, begin, args = 1, match.end(), []
        for end in range(begin, len(syntax)):
            char = syntax[end]
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            if (char == "," and depth == 1) or depth == 0:
                args.append(code[begin:end].strip())
                begin = end + 1
            if depth == 0:
                found.append(Call(match[1], match.start(), tuple(args)))
                break
    return found


def literal(value: str | None):
    try:
        return ast.literal_eval(value) if value is not None else None
    except (ValueError, SyntaxError):
        return None


def nonnegative(value: str | None, integer: bool = False) -> bool:
    number = literal(value)
    return (type(number) in ((int,) if integer else (int, float))
            and number >= 0 and (type(number) is int or math.isfinite(number)))


def lint(source: str) -> list[Result]:
    code, syntax = masked(source), masked(source, strings=True)
    all_calls, results = calls(source), []
    declarations = [call for call in all_calls if call.name == "strategy"]
    declaration = declarations[0] if len(declarations) == 1 else None
    anchor = declaration.start if declaration else 0

    def emit(rule: str, passed: bool, positions: list[int], detail: str):
        lines = tuple(sorted({source.count("\n", 0, p) + 1 for p in positions or [anchor]}))
        results.append(Result(rule, bool(passed), lines, detail))

    def setting(name: str) -> str | None:
        return declaration.named(name) if declaration else None

    def setting_position(name: str) -> int:
        match = re.search(rf"\b{re.escape(name)}\s*=", syntax[anchor:])
        return anchor + match.start() if match and setting(name) is not None else anchor

    orders = [c for c in all_calls if c.name in {
        "strategy.entry", "strategy.order", "strategy.exit", "strategy.close",
        "strategy.close_all", "strategy.cancel", "strategy.cancel_all",
    }]
    mutations = [m.start() for m in re.finditer(":=", syntax)]
    guarded_lines, stack = set(), []
    for number, line in enumerate(syntax.splitlines(), 1):
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if any(gate for _, gate in stack):
            guarded_lines.add(number)
        condition = re.match(r"\s*if\s+(.+)", line)
        if condition:
            expression = condition[1].strip()
            gate = bool(re.fullmatch(r"barstate\.isconfirmed(?:\s+and\s+.+)?", expression))
            gate = gate and not re.search(r"\bor\b", expression)
            stack.append((indent, gate))
    changes = [c.start for c in orders] + mutations
    unguarded = [p for p in changes if source.count("\n", 0, p) + 1 not in guarded_lines]
    emit("confirmed_bars", bool(orders) and not unguarded, unguarded or changes,
         "Order calls and := mutations require a positive enclosing confirmation gate.")
    emit("tick_calculation", setting("calc_on_every_tick") == "false", [setting_position("calc_on_every_tick")],
         "Declare calc_on_every_tick=false explicitly.")
    emit("order_timing", setting("process_orders_on_close") == "false", [setting_position("process_orders_on_close")],
         "Declare process_orders_on_close=false explicitly.")

    security = [c for c in all_calls if c.name.startswith("request.security")]
    bad = [c.start for c in security if c.name != "request.security"
           or c.named("lookahead") != "barmerge.lookahead_off"
           or not re.fullmatch(r"[\w.]+\[\s*1\s*\]", c.value("expression", 2) or "")]
    emit("htf_security", not bad, bad or [c.start for c in security],
         "Require lookahead_off and a direct series[1] expression per security call; absent calls are N/A.")
    pivots = [c for c in all_calls if c.name in {"ta.pivothigh", "ta.pivotlow"}]
    offset_index = {"plot": 7, "plotshape": 5, "plotchar": 5, "plotarrow": 4}
    plots = [(c, c.value("offset", offset_index[c.name])) for c in all_calls if c.name in offset_index]
    bad = [c.start for c, offset in plots if pivots and offset is not None and not nonnegative(offset)]
    emit("pivot_backdating", not bad, bad or [c.start for c in pivots],
         "When pivots exist, plot offsets must be nonnegative literals; confirm pivot usage manually.")
    sessions = [c for c in all_calls if c.name in {"time", "time_close"}
                and c.value("session", 1) is not None]
    bad = [c.start for c in sessions if c.value("timezone", 2) != "syminfo.timezone"
           and not re.fullmatch(r"[A-Za-z_]+/[A-Za-z_/+-]+", str(literal(c.value("timezone", 2))))]
    emit("session_timezone", not bad, bad or [c.start for c in sessions],
         "Use syminfo.timezone or an explicit named zone; manually confirm it is the exchange zone.")
    exits = [c for c in all_calls if c.name == "strategy.exit"]
    relative = {"profit", "loss", "trail_price", "trail_points", "trail_offset"}
    bad = [c.start for c in exits if any(c.named(k) in (None, "na") for k in ("stop", "limit"))
           or any(c.named(k) is not None for k in relative)]
    emit("absolute_exits", bool(exits) and not bad, bad or [c.start for c in exits],
         "Require stop and limit price arguments, excluding relative/trailing exits; review price units manually.")
    emit("limit_fill_assumption", setting("backtest_fill_limits_assumption") == "1", [setting_position("backtest_fill_limits_assumption")],
         "Declare backtest_fill_limits_assumption=1 for this fixture's trade-through assumption.")
    emit("explicit_costs", setting("commission_type") == "strategy.commission.cash_per_contract"
         and nonnegative(setting("commission_value")) and nonnegative(setting("slippage"), integer=True),
         [setting_position(k) for k in ("commission_type", "commission_value", "slippage")],
         "Require literal per-contract commission and slippage; cost-model equality is manual.")

    inputs = [c for c in all_calls if c.name == "input" or c.name.startswith("input.")]
    bad = []
    for call in inputs:
        options = literal(call.named("options"))
        bounded = (literal(call.named("minval")), literal(call.named("maxval")))
        finite_options = isinstance(options, list) and bool(options) and all(
            type(v) in (str, int, float) and (type(v) is not float or math.isfinite(v)) for v in options)
        limits = (all(type(v) in (int, float) and (type(v) is int or math.isfinite(v)) for v in bounded)
                  and bounded[0] <= bounded[1])
        if call.name != "input.bool" and not finite_options and not limits:
            bad.append(call.start)
    parameters = list(re.finditer(r"(?m)^[ \t]*(?:const\s+)?(?:int|float|string|bool)\s+[A-Z][A-Z_0-9]*\s*=.*$", code))
    bad += [m.start() for m in parameters if not m[0].lstrip().startswith("const ")
            and not re.search(r"\binput(?:\.\w+)?\s*\(", m[0])]
    emit("bounded_parameters", not bad, bad or [c.start for c in inputs] + [m.start() for m in parameters],
         "Bound inputs and declare uppercase fixed parameters const; parameter/grid completeness is manual.")
    title = literal(setting("shorttitle"))
    emit("shorttitle", isinstance(title, str) and 0 < len(title) <= 10, [anchor],
         "Require a literal shorttitle of 1–10 characters.")
    version = re.search(r'(?m)^const string SCRIPT_VERSION\s*=\s*["\']\d+\.\d+\.\d+["\']\s*$', code)
    pine_version = re.search(r"(?m)^//@version=6\s*$", source)
    emit("script_version", bool(version and pine_version), [version.start()] if version else [0],
         "Require //@version=6 and const string SCRIPT_VERSION; version increment history is manual.")
    drawings = [(c, "max_labels_count" if c.name == "label.new" else "max_lines_count")
                for c in all_calls if c.name in {"label.new", "line.new"}]
    bad = [c.start for c, key in drawings if not nonnegative(setting(key), integer=True)
           or not 1 <= literal(setting(key)) <= 500]
    emit("drawing_limits", not bad, bad or [c.start for c, _ in drawings],
         "Set a literal drawing limit from 1–500 when label.new or line.new is used; absent drawings are N/A.")
    alerts = [(c.start, c.named(key)) for c in all_calls
              for key in ("alert_message", "alert_profit", "alert_loss", "alert_trailing")
              if c.named(key) is not None]
    alerts += [(c.start, c.value("message", 0)) for c in all_calls if c.name == "alert"]
    alerts += [(c.start, c.value("message", 2)) for c in all_calls if c.name == "alertcondition"]
    bad = [p for p, message in alerts if not re.fullmatch(r"(?:\{\{[\w.]+\}\})+", str(literal(message)))]
    secrets = list(re.finditer(
        r"https?://|FAKE_TOKEN_DO_NOT_USE|\b(?:api[_-]?key|secret|token|password|account[_-]?id)\s*(?:=|:)",
        source, re.I))
    bad += [m.start() for m in secrets]
    emit("alert_safety", bool(alerts) and not bad, bad or [p for p, _ in alerts],
         "Use placeholder-only literal alerts; heuristic secret scan does not replace a full manual review.")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        path = args.file.resolve(strict=True)
        if path.suffix.lower() != ".pine" or not path.is_file() or path.stat().st_size > 1_000_000:
            raise ValueError("Expected a .pine file no larger than 1 MB")
        source = path.read_text(encoding="utf-8")
        if not source.strip() or "\x00" in source:
            raise ValueError("Expected nonempty Pine text without NUL bytes")
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print("Mechanical checks only. Does not replace manual replay checks or trade-list parity; not a compiler.")
    results = lint(source)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines = ",".join(map(str, result.lines))
        print(f"{status} {result.rule} line {lines}: {result.detail}")
    failures = sum(not result.passed for result in results)
    print(f"Summary: {len(results) - failures} PASS, {failures} FAIL. Manual checks: not run.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
