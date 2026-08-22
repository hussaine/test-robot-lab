#!/usr/bin/env bash
# Make the lab libraries importable and the scripts runnable.
#
#   bash ~/test-robot-lab/install.sh
#
# Called by setup-vm.sh and by update.sh after every pull, so `update` keeps
# robocam current with nothing to reinstall. Safe to re-run.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -d "$REPO_DIR/robocam" ]]; then
  echo "can't find the robocam folder next to install.sh" >&2
  exit 1
fi

chmod +x "$REPO_DIR/cvclient.py" 2>/dev/null || true
for script in "$REPO_DIR"/examples/*.py; do
  [[ -f "$script" ]] && chmod +x "$script"
done

# Make `import robocam` work from any directory, without installing anything. A
# .pth file in the user's site-packages just adds this repo to Python's path, so
# `update` keeps the library current with no reinstall step -- which a pip
# install would have needed after every pull. Same trick as roboshine on the
# robot side.
echo "making robocam importable ..."
SITE="$(python3 -c 'import site; print(site.getusersitepackages())' 2>/dev/null || true)"
if [[ -n "$SITE" ]]; then
  mkdir -p "$SITE"
  echo "$REPO_DIR" > "$SITE/robocam.pth"
  if python3 -c "import robocam" 2>/dev/null; then
    echo "  import robocam works from anywhere"
  else
    echo "  WARNING: wrote $SITE/robocam.pth but the import still fails" >&2
  fi
else
  echo "  WARNING: couldn't find your site-packages; robocam won't import" >&2
fi
