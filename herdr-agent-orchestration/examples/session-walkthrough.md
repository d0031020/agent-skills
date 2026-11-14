# Example session (illustrative)

These are the commands a lead runs to delegate one task to a Codex agent in a new pane. Pane IDs and names are made up.

```bash
# 1. Make a pane and start the agent. `agent start` waits until the agent is ready.
herdr pane split --pane w1:p1 --direction right      # prints the new pane, e.g. w1:p2
herdr agent start eng1 --kind codex --pane w1:p2

# 2. Check the target, then send a one-line prompt that points at the task file.
herdr agent get w1:p2
herdr agent prompt w1:p2 "Read tasks/017_parser.md and do it. Reply with one line when done."

# 3. Wait in the background (run it as a background job in your own harness).
herdr agent wait w1:p2 --until idle --until done --until blocked --timeout 1800000

# 4. When the wait returns, read the pane.
herdr agent read w1:p2

# 4a. If it is blocked on a trust dialog that offers a plain "Yes, continue" option:
herdr agent send-keys w1:p2 enter
herdr agent wait w1:p2 --timeout 1800000

# 5. Verify the result yourself. Do not trust "done".
cat RESULT.md
set -o pipefail; pytest -q | tee test.log; echo "exit=$?"
```

The decision rule: the task counts as accepted only after step 5 passes. Gate-type work also gets an independent reviewer agent.
