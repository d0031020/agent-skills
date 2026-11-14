# agent-skills

## What it is

A small, curated collection of [Agent Skills](https://www.anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation). An Agent Skill is a folder with a `SKILL.md` that a coding agent, such as Claude Code or Codex, can load on demand. Where it makes sense, each skill ships with examples, a verification tool and tests.

| Skill | What it does | Verification |
|---|---|---|
| [herdr-agent-orchestration](herdr-agent-orchestration/) | Lets a lead agent delegate work to other CLI agents running in [herdr](https://herdr.dev) panes, handle blocked dialogs, and verify results before accepting them | `tools/check_herdr_cli.sh` checks that the installed herdr exposes every command the skill uses |
| [pine-nonrepaint-parity-check](pine-nonrepaint-parity-check/) | A pre-push checklist for TradingView Pine strategies: non-repainting, parity with a Python backtest, compile hygiene and secret safety. Includes PASS/FAIL example scripts and a static checker | `pytest` (38 tests) |
| [prop-edge-target](prop-edge-target/) | Works backward from prop-account evaluation rules to the minimum per-trade edge (edge/sigma) a strategy needs. Includes a synthetic-data simulator | `pytest` (5 tests) |

## Why

Each skill turns a workflow that was used in practice into something repeatable and checkable. Every skill says plainly which parts were verified and which were not.

## Install

Copy a skill folder into your agent's skills directory. For Claude Code, that is `~/.claude/skills/<skill-name>/`. The Python-based skills declare their pinned dependencies in `requirements.txt`:

```bash
cd <skill-name>
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

## Usage

See each skill's own `README.md` and `SKILL.md`.

## How to verify / test

| Skill | Command | Result recorded 2026-11-14 |
|---|---|---|
| herdr-agent-orchestration | `tools/check_herdr_cli.sh` | 15/15 PASS on herdr 0.9.5 |
| pine-nonrepaint-parity-check | `python -m pytest -q` | 38 passed, in a fresh virtual environment |
| prop-edge-target | `python -m pytest -q` | 5 passed, in a fresh virtual environment |

Each skill's README lists what is **not** verified. For example, the Pine examples were syntax-parsed but not compiled in TradingView.

## Known limitations

- **herdr:** herdr's CLI and agent behavior change between versions. Re-check after upgrades.
- **Trading skills:** the two trading-related skills use only fictional, illustrative values and synthetic data. They contain no tuned strategy parameters and no performance claims. **Not financial or investment advice.**

## License

MIT. See [LICENSE](LICENSE). Each skill folder also carries a copy.

---

Drafted with AI assistance and reviewed by the author.
