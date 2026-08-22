#!/usr/bin/env bash
# One-time setup for a student VM. Ubuntu 24.04.
#
#   bash setup-vm.sh
#
# Installs what you need to reach a robot and run computer vision on its camera:
# git, OpenCV, ssh, and mDNS so `robot-7.local` resolves.
#
# VS Code is optional and not installed here. If you want it, get it from
# code.visualstudio.com; without it the 'eb' alias falls back to nano.
#
# Options:
#   --skip-upgrade    don't run 'apt upgrade'
#   --skip-vbox-tools don't install VirtualBox guest additions
#   --yes             don't ask for confirmation
#
# It also adds three aliases: update (pull the latest lab code and re-check the
# tools), sb (re-read ~/.bashrc) and eb (edit it).
#
# Safe to re-run.

set -uo pipefail

LOG="$HOME/vm-setup.log"
SKIP_UPGRADE=0
SKIP_VBOX=0
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    --skip-upgrade)    SKIP_UPGRADE=1 ;;
    --skip-vbox-tools) SKIP_VBOX=1 ;;
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
ok "architecture: $ARCH"

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]]; then
    ok "Ubuntu 24.04"
  else
    warn "this expects Ubuntu 24.04, found ${PRETTY_NAME:-unknown} -- continuing"
  fi
fi

# Deliberately not curl-only: curl is one of the things this script installs, and
# a minimal image may not have it. Reporting "no internet" when the real problem
# is a missing tool would send you looking in the wrong place.
network_reachable() {
  if command -v curl >/dev/null; then
    curl -fsS -m8 -o /dev/null https://github.com && return 0
  fi
  if command -v wget >/dev/null; then
    wget -q -T8 -O /dev/null https://github.com && return 0
  fi
  ping -c1 -W3 github.com >/dev/null 2>&1 && return 0
  return 1
}
network_reachable || die "can't reach github.com -- check the VM's network"
ok "internet reachable"

if (( ! ASSUME_YES )); then
  echo
  echo "This installs OpenCV, git, ssh and mDNS support. A few minutes."
  read -r -p "Continue? [y/N]: " reply
  [[ "$reply" =~ ^[Yy] ]] || { echo "cancelled"; exit 0; }
fi

# ---------------------------------------------------------------------------

step "Packages"

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

# All from apt, deliberately. Ubuntu 24.04 marks the system Python as externally
# managed (PEP 668), so 'pip install opencv-python' is refused outright -- but
# apt's python3-opencv sidesteps that entirely, with no virtualenv to explain or
# activate. It also pulls its own GUI dependencies, so cv2's windows just work.
#
# opencv-data is the one that's easy to miss: the pip wheel bundles the Haar
# cascade XML files, the Debian package does not. Without it, face detection
# loads an empty classifier and silently finds nothing.
sudo apt-get "${APT[@]}" install \
  git curl ca-certificates \
  python3-pip python3-numpy python3-opencv opencv-data \
  openssh-client \
  avahi-utils libnss-mdns \
  mosquitto-clients python3-paho-mqtt \
  ffmpeg v4l-utils \
  || die "installing packages failed"

ok "python3-opencv, python3-numpy   -- computer vision"
ok "opencv-data                     -- the Haar cascade files"
ok "openssh-client                  -- reaching the robot"
ok "avahi-utils, libnss-mdns        -- so robot-7.local resolves"
ok "mosquitto-clients, paho-mqtt    -- MQTT experiments"
ok "ffmpeg, v4l-utils               -- stream debugging"

step "VirtualBox guest additions"
if (( SKIP_VBOX )); then
  warn "skipped (--skip-vbox-tools)"
elif sudo apt-get "${APT[@]}" install virtualbox-guest-utils virtualbox-guest-x11; then
  ok "installed -- reboot for shared clipboard and window resizing"
else
  # These live in Ubuntu's universe pocket and aren't published for every
  # architecture, so failing here is plausible rather than alarming.
  warn "couldn't install them -- use the VirtualBox Devices menu instead"
  warn "(Devices > Insert Guest Additions CD image)"
fi

# ---------------------------------------------------------------------------

step "Shell aliases"

# Delegated so update.sh and this script can't drift apart.
bash "$(dirname "${BASH_SOURCE[0]}")/setup-aliases.sh" | sed 's/^/   /'

step "The robocam library"

# Same reason: install.sh is what update.sh runs too, so there's one way for
# `import robocam` to get set up.
bash "$(dirname "${BASH_SOURCE[0]}")/install.sh" | sed 's/^/   /'

# ---------------------------------------------------------------------------

step "Checking it worked"

python3 - <<'PY' || warn "OpenCV didn't import"
import glob
import cv2
import numpy
print(f"   ok   OpenCV {cv2.__version__}, numpy {numpy.__version__}")

# cv2.data exists in the pip wheels but not necessarily in Debian's package, so
# look in both places.
paths = []
if hasattr(cv2, "data"):
    paths.append(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
paths += glob.glob("/usr/share/opencv*/haarcascades/haarcascade_frontalface_default.xml")

found = next((p for p in paths if not cv2.CascadeClassifier(p).empty()), None)
if found:
    print(f"   ok   Haar cascades: {found}")
else:
    print("   !    Haar cascade files not found -- is opencv-data installed?")
PY

for tool in git ssh mosquitto_pub ffmpeg; do
  command -v "$tool" >/dev/null && ok "$tool" || warn "$tool is missing"
done

# VS Code is optional, and skipping it is a fine choice -- so this is a note
# rather than a warning. Warnings are counted and printed as problems at the end,
# and a deliberate choice shouldn't look like a broken setup.
if command -v code >/dev/null; then
  ok "code -- $(code --version 2>/dev/null | head -1)"
else
  echo "   --   no VS Code; 'eb' will use nano instead (code.visualstudio.com if you want it)"
fi

# robocam is a path entry rather than an installed package, so check the import
# the same way a student's script will.
if python3 -c "import robocam" 2>/dev/null; then
  ok "import robocam works"
else
  warn "robocam won't import -- see the warning further up"
fi

# mDNS is the one that quietly ruins an afternoon: without it robot-7.local
# doesn't resolve and nothing can reach the robot.
if systemctl is-active --quiet avahi-daemon; then
  ok "avahi is running (.local names should resolve)"
else
  warn "avahi isn't active; run: sudo systemctl enable --now avahi-daemon"
fi

# ---------------------------------------------------------------------------

echo
if (( PROBLEMS )); then
  echo "${YELLOW}${BOLD}Finished in $(elapsed) with $PROBLEMS warning(s).${OFF}"
else
  echo "${GREEN}${BOLD}Done in $(elapsed).${OFF}"
fi
cat <<EOF

Open a new terminal (so the aliases load), then:

    ssh robot@robot-1.local         connect to your robot
    python3 examples/first_look.py 1    look through its camera
    ./cvclient.py 1                 computer vision on its camera stream
    update                          get the latest lab code, any time

In your own scripts:

    import robocam as cam
    cam.connect(1)
    cam.showHelp()

Skeletons (robocam.getSkeleton) need one extra download, only if you want them:

    bash ~/test-robot-lab/setup-pose.sh

If robot-1.local can't be found, your VM's network adapter is probably set to
NAT. Change it to ${BOLD}Bridged Adapter${OFF} in the VirtualBox settings -- mDNS
names don't cross NAT.
EOF
