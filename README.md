# test-robot-lab

Code that runs on the **student's laptop or VM**, talking to a robot over the
network. The robot-side counterpart is
[test-robot-tools](https://github.com/sjaraza/test-robot-tools).

```
YOUR VM (Ubuntu 24.04)              ROBOT (Pi Zero 2 W)
robocam      ◄── MJPEG stream ───   hardware-encoded camera
cvclient.py  ◄─────────────────────
ssh          ───────────────────►   cockpit, roboshine
```

Heavy work happens here. A Pi Zero 2 W has four slow cores and 512MB, so it
captures and encodes; **all** the computer vision runs in your VM.

`robocam` is the library you write scripts against — the VM-side counterpart to
`roboshine` on the robot. `cvclient.py` is a ready-made viewer, useful before you
write anything of your own.

## One-time setup

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/sjaraza/test-robot-lab.git ~/test-robot-lab
bash ~/test-robot-lab/setup-vm.sh
```

The first line is there because a fresh Ubuntu desktop has no `git` — the script
installs it, but you need it to fetch the script in the first place.

Then **open a new terminal** so the aliases load. Reboot once as well, so the
VirtualBox guest additions take effect — you get a resizable window and a shared
clipboard.

Check it worked:

```bash
python3 -c "import robocam; robocam.showHelp()"
```

| Option | Effect |
|---|---|
| `--skip-upgrade` | don't run `apt upgrade` |
| `--skip-vbox-tools` | don't install the VirtualBox guest additions |
| `--yes` | no confirmation prompt |

Safe to re-run. Logged to `~/vm-setup.log`.

### What it installs, and why

| Package | Why |
|---|---|
| `python3-opencv`, `python3-numpy` | computer vision |
| `opencv-data` | the Haar cascade files — see below |
| `openssh-client` | reaching the robot |
| `avahi-utils`, `libnss-mdns` | so `robot-7.local` resolves at all |
| `mosquitto-clients`, `python3-paho-mqtt` | MQTT experiments |
| `ffmpeg`, `v4l-utils` | debugging streams outside Python |
| `git`, `python3-pip`, `curl` | the basics |
| `virtualbox-guest-utils`, `-x11` | shared clipboard and window resizing |

**Everything comes from apt, and there is no virtualenv.** That's deliberate:
Ubuntu 24.04 marks the system Python as externally managed (PEP 668), so
`pip install opencv-python` is refused outright — but apt's `python3-opencv`
sidesteps that with nothing to activate and nothing to explain. `python3` just
has `cv2`.

**`opencv-data` is the easy one to miss.** The pip wheel bundles the Haar cascade
XML files; the Debian package does not, they're in that separate package. Without
it face detection loads an empty classifier and silently finds nothing.

The trade for apt over pip: OpenCV is a version or two behind, and there's no
`cv2.aruco` (contrib isn't packaged). If you later need contrib or a pip package,
make a virtualenv then — `python3 -m venv ~/myenv`.

## Aliases it adds

| Alias | What it does |
|---|---|
| `update` | pull the latest lab code and re-check the tools |
| `sb` | re-read `~/.bashrc` after editing it |
| `eb` | edit `~/.bashrc` |

`eb` opens VS Code if you have it, and `nano` if you don't. VS Code is optional —
install it from [code.visualstudio.com](https://code.visualstudio.com) if you
want it, and nothing here minds either way.

## Keeping up to date

```bash
update
```

Pulls the latest lab code, refreshes the aliases, and checks the tools —
installing only what's actually missing. Built to be run often:

- **No `apt upgrade`**, so it takes seconds.
- **No sudo** unless something genuinely needs installing.
- **New aliases arrive automatically** as the lab grows.
- **`import robocam` is re-pointed** at the checkout, so a pull is all it takes.
- `update --check` reports what's missing and changes nothing.

It verifies `ffmpeg` by *running* it, not just finding it on PATH — a
present-but-broken ffmpeg looks fine to `command -v` and then shows up much later
as a stream that silently produces no frames.

## robocam — the camera library for your own scripts

The VM-side twin of `roboshine`. `roboshine` moves the robot; `robocam` sees
through its camera. Importable from anywhere once `setup-vm.sh` has run — no
virtualenv, no reinstall after a pull.

```python
import robocam as cam

cam.connect(3)                              # your robot's number or letter

while True:
    picture = cam.getFrame()                # newest frame, waits for a fresh one
    picture, faces = cam.findFaces(picture)

    if faces:
        print("nearest face at", faces[0]["cx"])

    if not cam.showImage(picture):          # q, Esc or closing the window
        break
```

Start the camera on the robot first — `cockpit`, item 7. `cam.showHelp()` prints
the whole API.

| Function | What it does |
|---|---|
| `connect(3)` | which robot to watch; `'A'` and `'robot-3.local'` also work |
| `getFrame()` | the newest picture, as an OpenCV image |
| `getFrameAge()` | how old that picture already was — your honest lag |
| `findFaces(picture)` | → picture with boxes, list of faces |
| `getSkeleton(picture)` | → picture with a skeleton, dict of joints |
| `showImage(picture)` | show a window; `False` once q, Esc or the X says stop |
| `saveImage(picture, name)` | write it to a file |
| `wait(seconds)` | pause |
| `showHelp()` | print everything |

**`findFaces()`** returns faces sorted biggest first, so `faces[0]` is the
nearest person. Each is a dict of `x`, `y`, `width`, `height`, `cx`, `cy`, `size`
— `cx` being the one you want for aiming, `size` for how close they are.

**`getSkeleton()`** returns joints keyed by name, so a script asks for the joint
it cares about and checks whether it was found:

```python
picture, joints = cam.getSkeleton(picture)

if "right_wrist" in joints and "right_shoulder" in joints:
    if joints["right_wrist"]["y"] < joints["right_shoulder"]["y"]:
        print("hand up!")                   # y counts down from the top
```

The 13 names, in `robocam.JOINTS`: `nose`, `left_shoulder`, `right_shoulder`,
`left_elbow`, `right_elbow`, `left_wrist`, `right_wrist`, `left_hip`,
`right_hip`, `left_knee`, `right_knee`, `left_ankle`, `right_ankle`. Hidden or
out-of-shot joints are simply absent. One person at a time, and it needs most of
a body in shot — a head-and-shoulders view finds nothing.

Both hand back a **copy** with the drawing on it, which is why they return two
things: the clean frame is still yours to use.

### Skeletons need one extra download

Faces and frames work with what `setup-vm.sh` already installed. Joints need a
pose model, once:

```bash
bash ~/test-robot-lab/setup-pose.sh
```

It tries MediaPipe first (a pip package — the only thing in this lab that isn't
apt, deliberately narrow), and falls back to an OpenPose-style model that apt's
own OpenCV can read. `update --check` reports which one you have, and treats
having neither as fine rather than as a problem.

### Examples

```bash
python3 ~/test-robot-lab/examples/first_look.py 3     # just the camera, and the lag
python3 ~/test-robot-lab/examples/see_faces.py 3      # faces, left/middle/right
python3 ~/test-robot-lab/examples/see_skeleton.py 3   # skeleton, hand-up detection
```

### Why getFrame() works the way it does

It hands back the **newest** frame and never the same one twice, waiting for a
fresh one if it has to. So a `while True` loop paces itself to the stream with no
`wait()`, and code slower than the stream drops frames instead of falling further
and further behind. `getFrameAge()` is the number to watch: if it climbs, lower
the robot's frame rate rather than letting lag build.

## cvclient.py — computer vision on the robot's camera

```bash
./cvclient.py 1                  # robot-1, Haar cascade faces
./cvclient.py A                  # robot-A -- letters work too
./cvclient.py 1 --detect motion  # frame differencing
./cvclient.py 1 --detect none    # just view, and measure latency
./cvclient.py 1 --no-window      # headless, print detections
```

A bare number or letter is treated as a robot label, so `A` means
`robot-A.local`. Anything with a dot in it is used as-is, so a full hostname or
an IP also works.

Start the stream first from the robot's cockpit (menu item 7). Edit
`process_frame(frame, state, detector)` to write your own vision code; `state` is
a dict that survives between frames.

The overlay reads:

```
 8.3 fps  cv 41.2ms  age  95ms
```

`age` is how stale the frame was when your code picked it up — the honest
end-to-end lag. High `age` with low `cv` means the network; high both means your
code is the bottleneck, so drop the stream's fps rather than letting lag build.

### Why not cv2.VideoCapture

It buffers internally, so CV slower than the stream falls progressively further
behind until the picture is seconds stale. `cvclient.py` keeps only the newest
frame and drops the rest, which is the right trade for anything that steers.

## Reaching the robot

```bash
ssh robot@robot-1.local
```

Plain `ssh` on this side for now. `mosh` — which echoes keystrokes locally and
survives dropouts, and is the nicer thing to have on a congested 2.4GHz AP — is
installed on the robots by `setup-mosh.sh` in test-robot-tools, but is
deliberately **not** part of the VM setup yet. One less moving part while the VM
side is still being proven; `sudo apt install mosh` is all it takes to add later.

## Troubleshooting

**`robot-1.local` not found.** Your VM's network adapter is on NAT. Change it to
**Bridged Adapter** in VirtualBox — mDNS names don't cross NAT. Everything else
here depends on this working.

**`cv2` not found.** Run `sudo apt install python3-opencv opencv-data`.

**Face detection finds nothing, ever.** The cascade files are missing:
`sudo apt install opencv-data`.

**Stream won't connect.** Start it on the robot: `cockpit`, item 7. Item 8 shows
the stream's log.

**`import robocam` fails.** Run `bash ~/test-robot-lab/install.sh`, then open a
new terminal. It writes a `.pth` file into your user site-packages pointing at
the checkout; `update` re-runs it after every pull.

**`getSkeleton()` says no pose model.** Run
`bash ~/test-robot-lab/setup-pose.sh`. Nothing else needs it.

**Skeletons are slow / the lag climbs.** Pose detection is much heavier than face
detection. Watch `getFrameAge()`, and lower the robot's frame rate rather than
letting the lag build — a stale picture is worse than a slow one.

