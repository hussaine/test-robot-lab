#!/usr/bin/env bash
# Pull the latest lab code and make sure the tools are still there. This is what
# the `update` alias runs, and it's meant to be run often.
#
#   bash ~/test-robot-lab/update.sh
#
# It pulls, refreshes the aliases, and checks the packages -- installing only
# what's actually missing. It does NOT run 'apt upgrade', so a routine update
# takes seconds and asks for no password unless something needs installing.
#
#   --check   report what's missing and change nothing

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
ok()   { echo "  ${GREEN}ok${OFF}   $*"; }
warn() { echo "  ${YELLOW}!${OFF}    $*"; }

# Everything setup-vm.sh installs. Kept here rather than there so `update` can
# repair a VM whose packages were removed, and so there's one list to maintain.
PACKAGES=(
  git curl ca-certificates
  python3-pip python3-numpy python3-opencv opencv-data
  openssh-client mosh
  avahi-utils libnss-mdns
  mosquitto-clients python3-paho-mqtt
  ffmpeg v4l-utils
)

# ---------------------------------------------------------------------------

if (( ! CHECK_ONLY )); then
  echo "${BOLD}Updating $REPO_DIR${OFF}"
  cd "$REPO_DIR" || exit 1

  BEFORE="$(git rev-parse --short HEAD 2>/dev/null || echo none)"
  if git pull --ff-only --quiet; then
    AFTER="$(git rev-parse --short HEAD)"
    if [[ "$BEFORE" == "$AFTER" ]]; then
      ok "already up to date ($AFTER)"
    else
      ok "updated $BEFORE -> $AFTER"
    fi
  else
    warn "couldn't fast-forward -- you may have local edits"
    warn "to discard them: git -C $REPO_DIR reset --hard origin/main"
  fi

  # New aliases get added as the lab grows, and a student who only ever types
  # `update` should still end up with them. A no-op when nothing changed.
  bash "$REPO_DIR/setup-aliases.sh"
fi

# ---------------------------------------------------------------------------

echo
echo "${BOLD}Checking the tools${OFF}"

MISSING=()

for tool in git ssh mosh mosquitto_pub; do
  if command -v "$tool" >/dev/null; then
    ok "$tool"
  else
    warn "$tool is missing"
    MISSING+=("$tool")
  fi
done

# ffmpeg gets run rather than merely located. A present-but-broken ffmpeg -- a
# library it links against having moved, say -- looks identical to a working one
# to 'command -v', and presents later as a stream that silently produces nothing.
# The probe runs inside its own shell so that if ffmpeg dies on a signal, the
# "Abort trap" notice goes to that shell's stderr and not the student's screen.
if ! command -v ffmpeg >/dev/null; then
  warn "ffmpeg is missing"
  MISSING+=("ffmpeg")
elif bash -c 'ffmpeg -hide_banner -version' >/dev/null 2>&1; then
  ok "ffmpeg"
else
  warn "ffmpeg is installed but won't run -- try: sudo apt install --reinstall ffmpeg"
  MISSING+=("ffmpeg")
fi

if python3 -c "import cv2, numpy" 2>/dev/null; then
  ok "OpenCV $(python3 -c 'import cv2; print(cv2.__version__)' 2>/dev/null)"
else
  warn "OpenCV won't import"
  MISSING+=("python3-opencv")
fi

# The Haar cascade files come from the separate opencv-data package. Without them
# face detection loads an empty classifier and silently finds nothing, which is
# far worse than an error.
if compgen -G "/usr/share/opencv*/haarcascades/haarcascade_frontalface_default.xml" >/dev/null \
   || python3 -c "import cv2, os, sys; sys.exit(0 if hasattr(cv2,'data') and os.path.isfile(cv2.data.haarcascades+'haarcascade_frontalface_default.xml') else 1)" 2>/dev/null; then
  ok "Haar cascade files"
else
  warn "Haar cascade files are missing (opencv-data)"
  MISSING+=("opencv-data")
fi

if command -v code >/dev/null; then
  ok "VS Code"
else
  warn "VS Code isn't on PATH -- install it from code.visualstudio.com"
fi

if ! command -v systemctl >/dev/null; then
  warn "no systemctl here -- can't check whether mDNS is running"
elif systemctl is-active --quiet avahi-daemon; then
  ok "mDNS (robot-N.local will resolve)"
else
  warn "avahi isn't running: sudo systemctl enable --now avahi-daemon"
fi

# ---------------------------------------------------------------------------

echo
if (( CHECK_ONLY )); then
  (( ${#MISSING[@]} )) && echo "missing: ${MISSING[*]}" || echo "${GREEN}everything present${OFF}"
  exit 0
fi

if (( ${#MISSING[@]} == 0 )); then
  echo "${GREEN}${BOLD}Up to date.${OFF}"
  exit 0
fi

# Only touch apt when something is genuinely absent, so the common case needs no
# sudo at all.
echo "Installing what's missing: ${MISSING[*]}"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq || warn "apt update had trouble, trying anyway"
if sudo apt-get install -y "${PACKAGES[@]}"; then
  echo
  echo "${GREEN}${BOLD}Done.${OFF}"
else
  echo
  echo "${RED}Some packages wouldn't install -- see the output above.${OFF}" >&2
  exit 1
fi
