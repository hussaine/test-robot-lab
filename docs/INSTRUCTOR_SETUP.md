# Physical AI & Robotics Bootcamp — Instructor Setup

This document describes the complete instructor setup used for the Physical AI robotics demos.

The setup consists of:

```text
PiCar-X Robot
    │
    ├── Raspberry Pi
    │      ├── camera stream
    │      ├── roboshine hardware API
    │      └── robot_server.py
    │
    │ Wi-Fi
    │
    ▼
Instructor Mac
    ├── robocam
    ├── OpenCV
    ├── MediaPipe
    ├── YOLO
    ├── robot_remote.py
    └── demo scripts
```

The robot is responsible for sensing and actuation.

The instructor computer performs the heavier perception and AI processing.

---

## 1. Repositories

Laptop-side repository:

```text
https://github.com/sjaraza/test-robot-lab
```

Robot-side tools:

```text
https://github.com/sjaraza/test-robot-tools
```

Local laptop checkout used during development:

```bash
/Users/hussain/codes/test-robot-lab
```

---

## 2. Robot Networking

### Recovery Network

The robots are configured to recognize the following Wi-Fi network:

```text
SSID: ShineLabs
Password: ShineLabs
```

A convenient recovery procedure is to create an iPhone hotspot with:

```text
Name: ShineLabs
Password: ShineLabs
```

On iPhone:

```text
Settings
→ General
→ About
→ Name
```

temporarily rename the phone:

```text
ShineLabs
```

Then:

```text
Settings
→ Personal Hotspot
→ Allow Others to Join
```

Use:

```text
Password: ShineLabs
```

If available, enable:

```text
Maximize Compatibility
```

The Pi Zero 2 W can then automatically connect to the hotspot.

Connect the Mac to the same hotspot.

Test:

```bash
ping robot-1.local
```

and:

```bash
ssh robot@robot-1.local
```

---

## 3. Adding Another Wi-Fi Network

Once SSH access is available:

```bash
nmcli device wifi list
```

To add another network:

```bash
sudo nmcli device wifi connect "YOUR_SSID" password "YOUR_PASSWORD"
```

The SSH session may immediately disconnect because the robot changes networks.

Connect the Mac to the new Wi-Fi and reconnect:

```bash
ssh robot@robot-1.local
```

Verify:

```bash
nmcli connection show
```

Do not delete the `ShineLabs` profile. It is useful as a recovery network.

---

## 4. Starting the Robot Camera

SSH:

```bash
ssh robot@robot-1.local
```

Run:

```bash
cockpit
```

Choose:

```text
7  Camera stream on / off
```

Confirm:

```text
cam live
```

You can quit `cockpit`; the stream continues running.

Useful diagnostics:

```text
8  Camera logs
9  Stop everything
10 Diagnostics
```

---

## 5. Robot Control Server

The laptop communicates with the robot through:

```text
pi/robot_server.py
```

Copy it to the robot:

```bash
cd /Users/hussain/codes/test-robot-lab
scp pi/robot_server.py robot@robot-1.local:~/
```

SSH into the Pi:

```bash
ssh robot@robot-1.local
```

Start the server:

```bash
python3 ~/robot_server.py
```

Expected output:

```text
robot server listening on 0.0.0.0:8765
```

Leave this terminal running.

The server supports a deliberately small command protocol:

```text
PING
STOP
STEER <angle>
FORWARD <speed>
DISTANCE
```

Robot-specific limits:

```text
steering: -30 ... +30 degrees
forward speed: 0 ... 100
```

The installed robot software uses a speed scale of `0–100`.

Important: earlier versions of `roboshine` documentation used a different speed scale. Always treat the actual robot installation as authoritative.

---

## 6. Test the Robot APIs Directly

### Steering

On the Pi:

```bash
python3 - <<'PY'
import roboshine as robot

robot.steer(-20)
input("LEFT - press Enter")
robot.steer(0)
input("STRAIGHT - press Enter")
robot.steer(20)
input("RIGHT - press Enter")

robot.steer(0)
PY
```

### Forward motion

Use a clear floor area:

```bash
python3 - <<'PY'
import time
import roboshine as robot

robot.steerStraight()
robot.driveForward(20)
time.sleep(0.5)
robot.stop()
PY
```

### Ultrasonic distance

Nothing in front:

```bash
python3 -c 'import roboshine as robot; print(robot.get_distance_cm())'
```

Expected:

```text
-1.0
```

This means no valid ultrasonic echo.

With an object nearby:

```bash
python3 -c 'import roboshine as robot; print(robot.get_distance_cm())'
```

Example:

```text
13.6
```

---

## 7. Instructor Mac Python Environments

Two Python environments were used.

Do not modify the known-working environments immediately before class.

### Environment A — Original CV Demos

```text
.venv
Python 3.14
```

Used for the original OpenCV / face demos.

Activate:

```bash
cd /Users/hussain/codes/test-robot-lab
source .venv/bin/activate
```

Example:

```bash
PYTHONPATH=. python examples/face_tracking_robot3.py robot-1.local
```

### Environment B — YOLO + MediaPipe

```text
.venv-yolo
Python 3.12
```

Used for:

- YOLO full-person detection
- MediaPipe pose estimation
- gesture control

Activate:

```bash
cd /Users/hussain/codes/test-robot-lab
source .venv-yolo/bin/activate
```

Known working versions:

```text
Python      3.12
NumPy       1.26.4
OpenCV      4.11.0
Torch       2.2.2
MediaPipe   0.10.20
Ultralytics installed
```

Verify:

```bash
python - <<'PY'
import numpy
print("numpy:", numpy.__version__)

import cv2
print("opencv:", cv2.__version__)

import torch
print("torch:", torch.__version__)

import mediapipe as mp
print("mediapipe:", mp.__version__)

from ultralytics import YOLO
print("YOLO: OK")
PY
```

Expected:

```text
numpy: 1.26.4
opencv: 4.11.0
torch: 2.2.2
mediapipe: 0.10.20
YOLO: OK
```

---

## 8. Important NumPy / OpenCV Compatibility

Do not upgrade NumPy to version 2 in `.venv-yolo`.

The working environment uses:

```text
numpy==1.26.4
```

Torch 2.2.2 on this Intel Mac produced errors with NumPy 2.x.

MediaPipe also works correctly with NumPy 1.26.4.

A conflicting package was:

```text
opencv-python 5.0.0.93
```

which required NumPy >=2.

It was removed:

```bash
python -m pip uninstall -y opencv-python
```

OpenCV contrib was then repaired:

```bash
python -m pip install \
    --force-reinstall \
    --no-deps \
    opencv-contrib-python==4.11.0.86
```

Do not reinstall `opencv-python 5.x`.

---

## 9. MediaPipe

MediaPipe is installed directly in `.venv-yolo`:

```bash
python -m pip install "mediapipe==0.10.20"
```

Do not use `setup-pose.sh` inside this Mac virtualenv because it attempts a `pip --user` install.

Verify:

```bash
python -c "import mediapipe as mp; print(mp.__version__)"
```

Verify robocam pose backend:

```bash
PYTHONPATH=. python -c 'import robocam, cv2; robocam._pose.backend(cv2); print(robocam._pose.describe())'
```

Expected:

```text
mediapipe
```

MediaPipe may print TensorFlow Lite / XNNPACK / OpenGL initialization messages. These are normal.

---

## 10. YOLO

The main model is:

```text
yolo11n.pt
```

It has already been downloaded locally.

The model is intentionally lightweight for real-time person detection.

Verify:

```bash
python -c "from ultralytics import YOLO; print('YOLO OK')"
```

The full-person detector uses COCO class:

```text
person
```

If multiple people are visible, the demo selects the largest detected person box as the target.

---

## 11. Demo Sequence

Recommended class sequence:

```text
DEMO 1
Classical Face Detection
    ↓
"I can see a face"

DEMO 2
Face → Steering
    ↓
"I can react to where you are"

DEMO 3
YOLO Person Follow
    ↓
"I can follow a human"

DEMO 4
MediaPipe Gesture Control
    ↓
"I can interpret body gestures"
```

---

## 12. Demo 1 — Classical Face Detection

Start camera from robot cockpit first.

On instructor Mac:

```bash
source .venv/bin/activate
```

Run:

```bash
python cvclient.py robot-1.local --detect faces
```

Teaching points:

- classical computer vision
- Haar-style face detector
- bounding box
- fragile to head rotation
- face becomes difficult to detect at distance

Useful experiment:

```text
look straight → detected
turn head → detection may disappear
move farther away → detection becomes harder
```

This motivates deep-learning perception.

---

## 13. Demo 2 — Face Steering

Use the known-good baseline:

```bash
source .venv/bin/activate
PYTHONPATH=. python examples/face_tracking_robot3.py robot-1.local
```

Concepts demonstrated:

```text
face center
   ↓
pixel error
   ↓
dead zone
   ↓
proportional steering
   ↓
physical servo
```

Controller concept:

```text
small error → small steering correction
large error → large steering correction
```

This is an intuitive introduction to proportional feedback control.

---

## 14. Demo 3 — Full-Person Follow

Activate:

```bash
source .venv-yolo/bin/activate
```

Run:

```bash
PYTHONPATH=. python examples/follow_person.py robot-1.local
```

The demo combines:

```text
YOLO person detector
        +
horizontal person position
        +
ultrasonic distance
        ↓
steering + forward movement
```

Person detection is more robust than face detection because:

- full body is larger in the frame
- works farther from camera
- does not require a frontal face
- remains useful when the person turns their head

This is the primary "Physical AI" demo.

---

## 15. Demo 4 — Gesture Control

Activate:

```bash
source .venv-yolo/bin/activate
```

Run:

```bash
PYTHONPATH=. python examples/gesture_control.py robot-1.local
```

Gesture mapping:

```text
Left hand raised
→ steer left + move slowly

Right hand raised
→ steer right + move slowly

No hands raised
→ move forward

Both hands raised
→ STOP

Pose lost
→ STOP
```

Pose commands are debounced across several frames to reduce jitter.

Concept:

```text
body pose
   ↓
gesture
   ↓
intent
   ↓
robot action
```

---

## 16. Safety Rules

All moving demos should follow these rules:

1. Test on the floor, never near a table edge.
2. Maintain clear space around the robot.
3. Keep speeds low.
4. Losing the perception target should stop drive motors.
5. Unknown ultrasonic distance should be treated as unsafe.
6. `Ctrl-C` should stop motors.
7. Closing the camera window should stop motors.
8. The Pi-side server should stop and straighten when the client disconnects.

Emergency robot control:

```bash
cockpit
```

then:

```text
9  Stop everything
```

---

## 17. Known Mechanical Issue

The current robot has noticeable resistance in the front wheels.

Observed behavior:

- steering servo commands work
- front wheels visibly turn correctly
- rear wheels drive correctly
- overall vehicle path may still drift to the right

A direct test showed the issue is mechanical rather than the vision controller.

Before future sessions, inspect:

- front wheel freedom
- steering linkage
- wheel alignment
- steering servo centering
- possible rubbing/contact
- rear motor balance

Do not compensate heavily in software until the mechanical issue is resolved.

---

## 18. Instructor Startup Checklist

Before students arrive:

```text
[ ] Robot battery charged
[ ] Robot connected to Wi-Fi
[ ] `ping robot-1.local` works
[ ] SSH works
[ ] Camera stream enabled via cockpit option 7
[ ] Latest robot_server.py copied to Pi
[ ] robot_server.py running on port 8765
[ ] Face detector tested
[ ] Face steering tested
[ ] .venv-yolo activates correctly
[ ] YOLO imports
[ ] yolo11n.pt exists locally
[ ] MediaPipe imports
[ ] robocam pose backend says "mediapipe"
[ ] follow_person.py tested
[ ] gesture_control.py tested
[ ] Clear floor area available
```

Recommended instructor terminal layout:

```text
Terminal 1
SSH to Pi
python3 ~/robot_server.py

Terminal 2
Instructor demos

Terminal 3
Emergency SSH / cockpit
```

---

## 19. Quick Recovery Commands

### Robot not reachable

Recreate:

```text
SSID: ShineLabs
Password: ShineLabs
```

Then:

```bash
ping robot-1.local
ssh robot@robot-1.local
```

### Camera not working

```bash
ssh robot@robot-1.local
cockpit
```

Choose:

```text
7
```

Check logs with:

```text
8
```

### Robot control unavailable

On Pi:

```bash
pkill -f robot_server.py
python3 ~/robot_server.py
```

### Stop everything

```bash
cockpit
```

choose:

```text
9
```

### Verify ultrasonic sensor

```bash
python3 -c 'import roboshine as robot; print(robot.get_distance_cm())'
```

### Verify YOLO environment

```bash
source .venv-yolo/bin/activate
python -c 'import numpy, cv2, torch, mediapipe; from ultralytics import YOLO; print("OK")'
```

---

## 20. Teaching Architecture

A useful architecture diagram for explaining the demos:

```text
                      Wi-Fi
┌────────────────┐                  ┌──────────────────────────┐
│    PiCar-X     │                  │      Instructor Mac      │
│                │                  │                          │
│ Camera ────────┼── video ───────→│ OpenCV / YOLO / MediaPipe│
│                │                  │            │             │
│ Ultrasonic ────┼── distance ─────→│         Policy           │
│                │                  │            │             │
│ Steering ←─────┼── commands ──────│            │             │
│ Motors   ←─────┼───────────────────│            │             │
└────────────────┘                  └──────────────────────────┘
```

The main conceptual loop is:

```text
SEE
 ↓
UNDERSTAND
 ↓
DECIDE
 ↓
ACT
 ↓
SEE AGAIN
```

That is the core idea behind the entire Physical AI session.
