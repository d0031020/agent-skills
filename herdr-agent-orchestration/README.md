# herdr-agent-orchestration

## What it is

An Agent Skill (`SKILL.md`) that teaches a lead coding agent, such as Claude Code, to delegate work to other CLI agents (Codex, Claude, Cursor and others) running in [herdr](https://herdr.dev) terminal panes. It covers the full loop:

1. Write a task file.
2. Send a one-line prompt.
3. Wait in the background.
4. Handle blocked dialogs.
5. Verify the result before accepting it.

## Why

When you drive several agents from one lead session, the same failures keep coming back:

- prompts lost to busy panes;
- prompts swallowed by permission dialogs;
- "idle" mistaken for "task accepted";
- the wrong pane targeted.

This skill writes down a workflow and failure cases that came from real delegated work, so the lead stops relearning them.

## Install

Copy the folder into your agent's skills directory, for example `~/.claude/skills/herdr-agent-orchestration/`. You also need:

- herdr installed and on `PATH`. The commands were checked on herdr 0.9.5.
- At least one supported agent CLI available to start in a pane.

## Usage

Once the skill is installed, the lead agent loads it when you ask it to delegate work to agents in herdr panes.

- `examples/task-template.md` is the task-file format the skill expects.
- `examples/session-walkthrough.md` shows one delegation end to end.

## How to verify / test

```bash
tools/check_herdr_cli.sh
```

The script checks that every herdr subcommand and flag the skill relies on exists in your installed herdr. Exit codes:

| Code | Meaning |
|---|---|
| 0 | All present |
| 1 | Something is missing. Re-read the skill against your version |
| 2 | herdr is not installed |

Results recorded on 2026-11-14:

- herdr 0.9.5: 15/15 PASS, exit 0.
- With herdr removed from `PATH`: `FAIL herdr not found on PATH`, exit 2.

What this does **not** verify:

- The check script only confirms that the subcommands and flags exist. It does not run a live delegation.
- The Codex free-text answer key sequence was verified once, on one Codex version. Codex's question UI may change.
- Agent status detection depends on herdr's detection for each agent kind.

## Known limitations

- herdr's CLI and its agent detection change between versions. Re-run the check script after every upgrade.
- Key sequences for dialogs differ between agents and agent versions. Always read the pane before sending keys.
- The skill assumes a single lead that routes all communication. It does not cover agents messaging each other.
- Check each agent vendor's terms before you drive its CLI automatically.

## License

MIT. See [LICENSE](LICENSE).

---

Drafted with AI assistance and reviewed by the author.
