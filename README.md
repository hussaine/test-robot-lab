# test-robot-lab

Code that runs on the **student's laptop or VM**, talking to a robot over the
network. The robot-side counterpart is
[test-robot-tools](https://github.com/sjaraza/test-robot-tools).

```
YOUR VM (Ubuntu 24.04)              ROBOT (Pi Zero 2 W)
cvclient.py  ◄── MJPEG stream ───   hardware-encoded camera
mosh / ssh   ───────────────────►   cockpit
```

Heavy work happens here. A Pi Zero 2 W has four slow cores and 512MB, so it
captures and encodes; your VM does the computer vision.

## One-time setup

```bash
git clone https://github.com/sjaraza/test-robot-lab.git ~/test-robot-lab
bash ~/test-robot-lab/setup-vm.sh
```

Then **open a new terminal** so the Python environment activates.

| Option | Effect |
|---|---|
| `--skip-vscode` | don't install VS Code (~100MB download) |
| `--skip-upgrade` | don't run `apt upgrade` |
| `--with-vbox-tools` | VirtualBox guest additions: shared clipboard, window resizing |
| `--yes` | no confirmation prompt |

Safe to re-run. Logged to `~/vm-setup.log`.

### What it installs, and why

| Package | Why |
|---|---|
| VS Code | the `.deb` for your architecture, detected automatically |
| `git`, `build-essential` | cloning, and building any pip package without a wheel |
| `python3-venv`, `python3-pip` | Ubuntu 24.04 needs a virtualenv — see below |
| `opencv-contrib-python` | CV. **contrib**, so ArUco markers and trackers are included |
| `openssh-client`, `mosh` | reaching the robot |
| `avahi-utils`, `libnss-mdns` | so `robot-7.local` resolves at all |
| `mosquitto-clients` | `mosquitto_pub` / `mosquitto_sub` for MQTT experiments |
| `ffmpeg`, `v4l-utils` | debugging streams outside Python |
| `libgl1` and friends | OpenCV's own windows won't open without them |

**On VS Code and PATH:** nothing to do. The `.deb` ships `/usr/bin/code`, and it
registers Microsoft's apt repo, so `apt upgrade` keeps VS Code current from then
on. That's why the script prefers the `.deb` over a tarball.

**On Python:** Ubuntu 24.04 marks the system Python as externally managed
(PEP 668), so `pip install opencv-contrib-python` is refused outright. The script
creates a virtualenv at `~/.venvs/robotlab` and auto-activates it from
`~/.bashrc`, so `python3` just has `cv2` and students never meet the problem.

**On contrib:** the plain `opencv-python` wheel lacks `cv2.aruco`, and Ubuntu's
`python3-opencv` lacks it too. ArUco markers are the easiest way to give a robot
something reliable to see, so contrib is worth the slightly larger download.

## cvclient.py — computer vision on the robot's camera

```bash
./cvclient.py 1                  # robot-1, Haar cascade faces
./cvclient.py 1 --detect motion  # frame differencing
./cvclient.py 1 --detect none    # just view, and measure latency
./cvclient.py 1 --no-window      # headless, print detections
```

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

## mosh instead of ssh

```bash
mosh robot@robot-1.local
```

Better than `ssh` on a congested 2.4GHz AP: keystrokes echo locally instead of
waiting for a round trip, and the session survives dropouts, roaming and a closed
lid. Needs installing on **both** ends — `setup-vm.sh` does this side, and
`setup-mosh.sh` in test-robot-tools does the robot.

## Troubleshooting

**`robot-1.local` not found.** Your VM's network adapter is on NAT. Change it to
**Bridged Adapter** in VirtualBox — mDNS names don't cross NAT. Everything else
here depends on this working.

**`cv2` not found.** Open a new terminal; the virtualenv activates on login.
Or run `source ~/.venvs/robotlab/bin/activate` in the current one.

**Stream won't connect.** Start it on the robot: `cockpit`, item 7. Item 8 shows
the stream's log.

**`mosh` fails but `ssh` works.** Usually mosh missing on one end, a non-UTF-8
locale on the robot, or UDP 60000-61000 blocked.
