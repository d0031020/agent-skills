#!/usr/bin/env bash
# Checks that every herdr subcommand and flag this skill relies on exists in the installed herdr.
# Exit 0: all found. Exit 1: something is missing (re-read the skill against your herdr version). Exit 2: herdr not installed.
set -uo pipefail

command -v herdr >/dev/null 2>&1 || { echo "FAIL herdr not found on PATH"; exit 2; }
echo "herdr version: $(herdr --version 2>&1 | head -1)"

fail=0
check() {  # check "<subcommand words>" "<required token in its --help>"
  local help
  help="$(herdr $1 --help 2>&1)"
  if grep -q -- "$2" <<<"$help"; then echo "PASS herdr $1 :: $2"; else echo "FAIL herdr $1 :: $2"; fail=1; fi
}

check "agent" "get"
check "agent" "read"
check "agent" "prompt"
check "agent" "wait"
check "agent" "send-keys"
check "agent" "start"
check "agent wait" "--until"
check "agent wait" "--timeout"
check "agent wait" "blocked"
check "agent start" "--kind"
check "agent start" "--pane"
check "agent start" "--timeout"
check "pane" "split"
check "pane" "send-text"
check "pane split" "--direction"

exit $fail
