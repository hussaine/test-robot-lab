#!/usr/bin/env bash
# One-time setup for a student VM. Ubuntu 24.04.
#
#   bash setup-vm.sh
#
# Installs VS Code, git, Python tooling and OpenCV (contrib), plus the bits you
# need to actually reach a robot: mosh, and mDNS so `robot-7.local` resolves.
#
# Options:
#   --skip-vscode     don't install VS Code (about 100MB to download)
#   --skip-upgrade    don't run 'apt upgrade'
#   --with-vbox-tools also install VirtualBox guest additions (clipboard, resize)
#   --yes             don't ask for confirmation
#
# Safe to re-run.

set -uo pipefail

LOG="$HOME/vm-setup.log"
VENV="$HOME/.venvs/robotlab"
SKIP_VSCODE=0
SKIP_UPGRADE=0
WITH_VBOX=0
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    --skip-vscode)     SKIP_VSCODE=1 ;;
    --skip-upgrade)    SKIP_UPGRADE=1 ;;
    --with-vbox-tools) WITH_VBOX=1 ;;
    --yes|-y)          ASSUME_YES=1 ;;
    -h|--help)
      awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print; next } NR>1 { exit }' "$0"
      exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

exec > >(tee -a "$LOG") 2>&1

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
STEP=0
STARTED=$SECONDS
PROBLEMS=0

step() { STEP=$((STEP + 1)); echo; echo "${BOLD}== $STEP. $* ==${OFF}"; }
ok()   { echo "   ${GREEN}ok${OFF}   $*"; }
warn() { echo "   ${YELLOW}!${OFF}    $*"; PROBLEMS=$((PROBLEMS + 1)); }
die()  { echo "   ${RED}fail${OFF} $*"; echo; echo "See $LOG"; exit 1; }
elapsed() { local t=$((SECONDS - STARTED)); printf '%dm%02ds' $((t/60)) $((t%60)); }

# ---------------------------------------------------------------------------

echo "${BOLD}Student VM setup${OFF}   $(date)"
echo "log: $LOG"

step "Checking the basics"

[[ $EUID -eq 0 ]] && die "run as your normal user, not with sudo -- it calls sudo itself"
sudo -v 2>/dev/null || die "sudo isn't working for this user"
ok "sudo works"

ARCH="$(dpkg --print-architecture)"
case "$ARCH" in
  amd64|arm64) ok "architecture: $ARCH" ;;
  *) die "unexpected architecture '$ARCH' -- expected amd64 or arm64" ;;
esac

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]]; then
    ok "Ubuntu 24.04"
  else
    warn "this expects Ubuntu 24.04, found ${PRETTY_NAME:-unknown} -- continuing"
  fi
fi

curl -fsS -m8 -o /dev/null https://github.com || die "no internet connection"
ok "internet reachable"

if (( ! ASSUME_YES )); then
  echo
  echo "This installs VS Code, git, Python tooling, OpenCV and mosh."
  read -r -p "Continue? [y/N]: " reply
  [[ "$reply" =~ ^[Yy] ]] || { echo "cancelled"; exit 0; }
fi

# ---------------------------------------------------------------------------

step "System packages"

export DEBIAN_FRONTEND=noninteractive
APT=(-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)

sudo apt-get update || die "apt update failed"
ok "package lists updated"

if (( SKIP_UPGRADE )); then
  warn "skipping apt upgrade (--skip-upgrade)"
else
  sudo apt-get "${APT[@]}" upgrade || die "apt upgrade failed"
  ok "system upgraded"
fi

# Grouped by why they're here, because "why is this installed" is a fair question.
sudo apt-get "${APT[@]}" install \
  git curl ca-certificates build-essential \
  python3-pip python3-venv python3-dev \
  openssh-client mosh \
  avahi-utils libnss-mdns \
  mosquitto-clients \
  ffmpeg v4l-utils \
  libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
  || die "installing packages failed"

ok "git, build tools, python3-venv"
ok "openssh-client, mosh          -- reaching the robot"
ok "avahi-utils, libnss-mdns      -- so robot-7.local resolves"
ok "mosquitto-clients             -- MQTT experiments"
ok "ffmpeg, v4l-utils             -- stream debugging"
ok "libgl1 and friends            -- OpenCV's windows need these"

if (( WITH_VBOX )); then
  step "VirtualBox guest additions"
  if sudo apt-get "${APT[@]}" install virtualbox-guest-utils virtualbox-guest-x11; then
    ok "installed -- reboot for shared clipboard and window resizing"
  else
    warn "couldn't install them; install from the VirtualBox Devices menu instead"
  fi
fi

# ---------------------------------------------------------------------------

step "VS Code"

if (( SKIP_VSCODE )); then
  warn "skipped (--skip-vscode)"
elif command -v code >/dev/null; then
  ok "already installed: $(code --version 2>/dev/null | head -1)"
else
  case "$ARCH" in
    amd64) SLUG="linux-deb-x64" ;;
    arm64) SLUG="linux-deb-arm64" ;;
  esac
  DEB="/tmp/vscode-$ARCH.deb"
  echo "   downloading the $ARCH build, about 100MB ..."
  if curl -fL --progress-bar -o "$DEB" \
       "https://update.code.visualstudio.com/latest/$SLUG/stable"; then
    # 'apt install ./file.deb' rather than dpkg -i, so dependencies resolve.
    sudo apt-get "${APT[@]}" install "$DEB" || die "installing VS Code failed"
    rm -f "$DEB"
    # No PATH work needed: the .deb ships /usr/bin/code, and it also registers
    # Microsoft's apt repo so 'apt upgrade' keeps VS Code current from now on.
    ok "installed: $(code --version 2>/dev/null | head -1)"
    ok "'code' is on PATH already (the .deb provides /usr/bin/code)"
  else
    warn "download failed -- install VS Code manually from code.visualstudio.com"
  fi
fi

# ---------------------------------------------------------------------------

step "Python environment with OpenCV"

# Ubuntu 24.04 marks the system Python as externally managed (PEP 668), so
# 'pip install' into it refuses outright. A virtualenv is the clean answer, and
# auto-activating it means students never have to think about that.
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV" || die "couldn't create the virtualenv at $VENV"
  ok "created $VENV"
else
  ok "$VENV already exists"
fi

"$VENV/bin/pip" install --quiet --upgrade pip wheel || warn "couldn't upgrade pip"

# --only-binary so a missing wheel fails in seconds instead of trying to compile
# OpenCV, which would take hours in a VM.
if "$VENV/bin/pip" install --only-binary=:all: opencv-contrib-python numpy; then
  ok "opencv-contrib-python + numpy"
else
  warn "no OpenCV wheel for $ARCH -- falling back to Ubuntu's python3-opencv"
  warn "(that build has no contrib modules, so ArUco and trackers won't be there)"
  sudo apt-get "${APT[@]}" install python3-opencv || warn "that failed too"
fi

# Auto-activate, as one managed block so re-running can't stack duplicates.
BEGIN="# --- robotlab python (managed by setup-vm.sh) ---"
END="# --- end robotlab python ---"
BASHRC="$HOME/.bashrc"
touch "$BASHRC"
if grep -qF "$BEGIN" "$BASHRC"; then
  ok "virtualenv already activates on login"
else
  {
    echo
    echo "$BEGIN"
    echo "[ -f \"$VENV/bin/activate\" ] && source \"$VENV/bin/activate\""
    echo "$END"
  } >> "$BASHRC"
  ok "added activation to ~/.bashrc"
fi

# ---------------------------------------------------------------------------

step "Checking it worked"

"$VENV/bin/python" - <<'PY' || warn "OpenCV didn't import from the virtualenv"
import cv2, numpy
print(f"   ok   OpenCV {cv2.__version__}, numpy {numpy.__version__}")
haar = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
print(f"   {'ok  ' if not cv2.CascadeClassifier(haar).empty() else 'FAIL'} "
      "Haar cascade data present")
print(f"   {'ok  ' if hasattr(cv2, 'aruco') else 'FAIL'} "
      "contrib modules (cv2.aruco) present")
PY

for tool in git ssh mosh mosquitto_pub ffmpeg; do
  if command -v "$tool" >/dev/null; then
    ok "$tool"
  else
    warn "$tool is missing"
  fi
done

# mDNS is the one that quietly ruins the afternoon: without it robot-7.local
# doesn't resolve and nothing can reach the robot.
if getent hosts ubuntu.local >/dev/null 2>&1 || systemctl is-active --quiet avahi-daemon; then
  ok "mDNS is running (.local names should resolve)"
else
  warn "avahi doesn't look active; run: sudo systemctl enable --now avahi-daemon"
fi

# ---------------------------------------------------------------------------

echo
if (( PROBLEMS )); then
  echo "${YELLOW}${BOLD}Finished in $(elapsed) with $PROBLEMS warning(s).${OFF}"
else
  echo "${GREEN}${BOLD}Done in $(elapsed).${OFF}"
fi
cat <<EOF

Open a NEW terminal (so the Python environment activates), then:

    mosh robot@robot-1.local        connect to your robot
    ./cvclient.py 1                 computer vision on its camera stream

If robot-1.local can't be found, your VM's network adapter is probably set to
NAT. Change it to ${BOLD}Bridged Adapter${OFF} in the VirtualBox settings -- mDNS
names don't cross NAT.
EOF
