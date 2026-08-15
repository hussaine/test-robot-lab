#!/usr/bin/env bash
# Add the lab aliases to ~/.bashrc. Called by setup-vm.sh and update.sh, or run
# it directly:
#
#   bash ~/test-robot-lab/setup-aliases.sh
#
# Afterwards:
#   update   pull the latest lab code and re-check the tools
#   sb       re-read ~/.bashrc after editing it
#   eb       edit ~/.bashrc in VS Code
#
# Safe to re-run. It rewrites its own managed block rather than appending, and
# does nothing at all when the block already matches -- so running it often
# leaves no trace.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASHRC="$HOME/.bashrc"
BEGIN="# --- robotlab (managed by setup-vm.sh) ---"
END="# --- end robotlab ---"

touch "$BASHRC"

TMP="$(mktemp)"
NEW="$(mktemp)"
trap 'rm -f "$TMP" "$NEW"' EXIT

# Drop our block, plus any loose copies of these aliases from hand-editing or an
# older version of the script.
awk -v b="$BEGIN" -v e="$END" '
  $0 == b { inblock = 1; next }
  $0 == e { inblock = 0; next }
  inblock { next }
  /^alias (sb|eb|update|runvenv)=/ { next }
  { print }
' "$BASHRC" > "$TMP"

{
  # Collapse trailing blank lines the removal left behind. Without this each run
  # appends another, the file never compares equal, and it grows every time.
  awk 'BEGIN { blank = 0 }
       { if ($0 == "") { blank++ } else { while (blank > 0) { print ""; blank-- }; print } }' "$TMP"
  echo
  echo "$BEGIN"
  echo "alias update='bash $REPO_DIR/update.sh'"
  echo "alias sb='source ~/.bashrc'"
  echo "alias eb='code ~/.bashrc'"
  echo "$END"
} > "$NEW"

if cmp -s "$NEW" "$BASHRC"; then
  echo "aliases already up to date"
  exit 0
fi

cp "$BASHRC" "$BASHRC.labbak"        # one backup, overwritten, not one per run
cat "$NEW" > "$BASHRC"

echo "aliases written to $BASHRC"
echo "  (previous version saved as ~/.bashrc.labbak)"
echo
echo "Run this once to use them now:   source ~/.bashrc"
echo "Then:  update   sb   eb"
