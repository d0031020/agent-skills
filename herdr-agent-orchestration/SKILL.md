---
name: herdr-agent-orchestration
description: "How a lead Claude session drives other CLI coding agents in herdr panes: task file, one-line prompt, background wait, then verify the result. Use when you delegate work to agents running in herdr panes and must handle busy panes, blocked dialogs and fresh pane startup."
---

# Orchestrating CLI agents through herdr

This skill covers one job: hand a task to an agent in a herdr pane, then collect and verify the result reliably.

**Provenance:** field-tested by a lead session that delegated a few dozen tasks to engineer and reviewer agents in herdr panes. The failure cases below were observed in that work.

The commands were checked against `herdr agent --help` and `herdr pane --help` on herdr 0.9.5. The free-text answer sequence for Codex question prompts was verified once. Other key sequences can change between agent versions, so read the pane before you send keys.

## Workflow

1. **Write a task file**, for example `tasks/<id>_<name>.md`. Give it a goal, inputs, write scope, outputs, acceptance tests and a time box. The detail lives in the file, not in the prompt. See `examples/task-template.md`.
2. **Check the target pane first.** Run `herdr agent get <pane>` and `herdr agent read <pane>`.
   - Use explicit pane IDs. Never guess a pane from its name.
   - Status `idle` or `done` means the agent's *turn* ended. It does not mean the task is accepted.
3. **Send one short prompt that points at the file:**
   `herdr agent prompt <pane> "Read tasks/<id>_<name>.md and do it. Reply with one line when done."`
4. **Wait in the background. Do not poll.** Run this as a background command:
   `herdr agent wait <pane> --until idle --until done --until blocked --timeout <ms>`
   A timeout only ends your observation. It does not prove the agent stopped.
5. **When the wait returns, read the pane.**
   - If it is `blocked`, go to the next section.
   - Otherwise, open the result file the task asked for.
6. **Verify the result yourself.**
   - Read the code and the outputs, re-run the tests and check the real exit codes.
   - Gate-type work also gets an independent reviewer agent that re-runs it.
   - Then update your state and decision files.

## Blocked dialogs and question prompts

- Read the pane (`herdr agent read <pane>`) to see what it is asking.
- A permission or trust dialog swallows any prompt you send.
  - Answer it with `herdr agent send-keys <pane> <key>...`. For example, send `enter`, or arrow keys and then `enter` to pick an option.
  - Use `esc` for Escape.
- Some agents show a multiple-choice question. Pick an option with the arrow keys and `enter`.
- **To answer a Codex question prompt with free text** (verified once; re-read the pane between steps):
  1. `herdr agent send-keys <pane> shift+left` opens the question.
  2. Send `down` twice to move to the "Other" option.
  3. `herdr pane send-text <pane> "<your answer>"` types the free text.
  4. Send `enter` to submit it.
  5. If you need to revise, `shift+right` goes back to the previous question.
- **Never answer a dialog that grants access to money, accounts or credentials.** Escalate it to the human owner.
- After answering, wait again and re-read the pane. Resend the original prompt only if the pane is idle.

## Fresh panes

1. Run `herdr pane split --pane <existing> --direction right` (or `down`) to create a new pane. Note its ID from the output.
2. Make sure the pane sits at an interactive shell prompt. Then run:
   `herdr agent start <name> --kind <claude|codex|...> --pane <id>`
   `agent start` waits until the agent is ready for input. Use `--timeout <ms>` to change the default of 30000.
3. Send the first prompt. Tell the agent to read the project README and its role file.

## Failure cases seen

- **Busy pane on start or prompt.** The agent was still working, so the prompt was queued or lost. Check the status first and wait for idle.
- **A dialog swallowed the prompt.** The prompt text went into a dialog's input field. Read the pane, clear the dialog, then resend.
- **"Done" was treated as accepted.** Idle only means the turn ended. Always check the artifacts.
- **Ambiguous mapping.** Two panes can report the same session ID. Select targets by pane ID plus working directory.
- **Chained commands with `| tee`.** Use `set -o pipefail`, or the exit code is hidden.

## Rules for the lead

- **Agents do not prompt each other.** Route everything through the lead, so there is one source of truth.
- **Keep prompts short.** Put the detail in the task file.
- **Never give delegated agents credentials or the ability to spend money.**

## Risks

- herdr's CLI and its agent detection change between versions. Run `tools/check_herdr_cli.sh` or `herdr agent --help` again after every upgrade.
- Check each agent vendor's terms before you drive its CLI automatically.
- Automated key presses act on whatever the pane currently shows. Always read the pane first.
