#!/usr/bin/env bash
# Install what robocam.getSkeleton() needs. Run once, only if you want skeletons.
#
#   bash ~/test-robot-lab/setup-pose.sh
#
# Nothing else in the lab needs this -- getFrame() and findFaces() work with the
# packages setup-vm.sh already installed.
#
# There are two ways to get body joints, and this tries them in order:
#
#   1. MediaPipe, a pip package. Best quality, no model file to look after.
#   2. An OpenPose-style Caffe model that apt's OpenCV can read on its own.
#      Bigger download, slower, but no pip involved.
#
# Options:
#   --dnn-only     skip MediaPipe, go straight to the model download
#   --yes          don't ask

set -uo pipefail

MODEL_DIR="$HOME/.robocam/models"
PROTOTXT_URL="https://raw.githubusercontent.com/CMU-Perceptual-Computing-Lab/openpose/master/models/pose/mpi/pose_deploy_linevec_faster_4_stages.prototxt"
DNN_ONLY=0
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    --dnn-only) DNN_ONLY=1 ;;
    --yes|-y)   ASSUME_YES=1 ;;
    -h|--help)  awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print; next } NR>1 { exit }' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
ok()   { echo "  ${GREEN}ok${OFF}   $*"; }
warn() { echo "  ${YELLOW}!${OFF}    $*"; }

echo "${BOLD}Pose detection for robocam.getSkeleton()${OFF}"

if python3 -c "import robocam, cv2; robocam._pose.backend(cv2)" 2>/dev/null; then
  ok "already working -- nothing to do"
  python3 -c "import robocam; print('  using:', robocam._pose.describe())" 2>/dev/null || true
  exit 0
fi

ARCH="$(dpkg --print-architecture 2>/dev/null || uname -m)"
echo "  architecture: $ARCH"

# --- 1. MediaPipe ----------------------------------------------------------

if (( ! DNN_ONLY )); then
  echo
  echo "${BOLD}Trying MediaPipe${OFF}"

  # Ubuntu 24.04 marks the system Python as externally managed (PEP 668), so a
  # plain `pip install` is refused outright. This is the one place in the whole
  # lab that steps outside apt, so it's deliberately narrow: one package, into
  # the user's own directory, and nothing else in the VM changes.
  if [[ "$ARCH" != "amd64" && "$ARCH" != "x86_64" ]]; then
    warn "MediaPipe's Linux wheels are mainly built for amd64;"
    warn "on $ARCH this may simply not be available -- the fallback below covers it"
  fi

  if (( ! ASSUME_YES )); then
    read -r -p "  install the mediapipe pip package? [Y/n]: " reply
    [[ "${reply:-y}" =~ ^[Nn] ]] && DNN_ONLY=1
  fi
fi

if (( ! DNN_ONLY )); then
  if python3 -m pip install --user --break-system-packages mediapipe; then
    if python3 -c "import mediapipe" 2>/dev/null; then
      ok "mediapipe installed"
      echo
      echo "Try it:  python3 ~/test-robot-lab/examples/see_skeleton.py 3"
      exit 0
    fi
    warn "mediapipe installed but won't import"
  else
    warn "pip couldn't install mediapipe on this machine"
  fi
  echo "  falling back to the OpenCV model ..."
fi

# --- 2. OpenPose-style model for cv2.dnn -----------------------------------

echo
echo "${BOLD}Setting up the OpenCV pose model${OFF}"
mkdir -p "$MODEL_DIR"

if ! curl -fsSL --retry 2 -o "$MODEL_DIR/pose.prototxt" "$PROTOTXT_URL"; then
  warn "couldn't download the network description from"
  warn "$PROTOTXT_URL"
  exit 1
fi
ok "network description -> $MODEL_DIR/pose.prototxt"

# The weights are the awkward part. CMU's own download host has been unreliable
# for years and the community mirrors come and go, so this script does NOT bake
# in a URL that may 404 by the time you run it -- give it one, or drop the file
# in by hand.
if [[ -n "${POSE_MODEL_URL:-}" ]]; then
  echo "  downloading weights (about 200MB) ..."
  if curl -fL --retry 2 -o "$MODEL_DIR/pose.caffemodel" "$POSE_MODEL_URL"; then
    ok "weights -> $MODEL_DIR/pose.caffemodel"
  else
    warn "that URL didn't work"
    rm -f "$MODEL_DIR/pose.caffemodel"
    exit 1
  fi
elif compgen -G "$MODEL_DIR/*.caffemodel" > /dev/null; then
  ok "weights already in $MODEL_DIR"
else
  echo
  warn "the weights file is missing, and it's the one thing this script won't guess at."
  cat <<EOF

  Get a MediaPipe-free OpenPose MPI model -- the file is called
  pose_iter_160000.caffemodel (about 200MB) -- and put it here:

      $MODEL_DIR/pose.caffemodel

  Or, if you have a working download link:

      POSE_MODEL_URL="https://..." bash ~/test-robot-lab/setup-pose.sh --dnn-only

  Then check it with:

      python3 -c "import robocam, cv2; robocam._pose.backend(cv2); \\
                  print(robocam._pose.describe())"
EOF
  exit 1
fi

if python3 -c "import robocam, cv2; robocam._pose.backend(cv2)" 2>/dev/null; then
  ok "getSkeleton() is ready"
  python3 -c "import robocam; print('  using:', robocam._pose.describe())"
else
  warn "the model is in place but robocam still can't load it"
  exit 1
fi
