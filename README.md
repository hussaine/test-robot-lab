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

Install **VS Code** yourself first, from
[code.visualstudio.com](https://code.visualstudio.com) — the script doesn't do
it. Then:

```bash
git clone https://github.com/sjaraza/test-robot-lab.git ~/test-robot-lab
bash ~/test-robot-lab/setup-vm.sh
```

Then **open a new terminal** so the aliases load.

| Option | Effect |
|---|---|
| `--skip-upgrade` | don't run `apt upgrade` |
| `--with-vbox-tools` | VirtualBox guest additions: shared clipboard, window resizing |
| `--yes` | no confirmation prompt |

Safe to re-run. Logged to `~/vm-setup.log`.

### What it installs, and why

| Package | Why |
|---|---|
| `python3-opencv`, `python3-numpy` | computer vision |
| `opencv-data` | the Haar cascade files — see below |
| `openssh-client`, `mosh` | reaching the robot |
| `avahi-utils`, `libnss-mdns` | so `robot-7.local` resolves at all |
| `mosquitto-clients`, `python3-paho-mqtt` | MQTT experiments |
| `ffmpeg`, `v4l-utils` | debugging streams outside Python |
| `git`, `python3-pip`, `curl` | the basics |

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
| `sb` | re-read `~/.bashrc` after editing it |
| `eb` | open `~/.bashrc` in VS Code |

`eb` needs VS Code on your PATH. The script checks and warns if `code` isn't
found.

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

**`cv2` not found.** Run `sudo apt install python3-opencv opencv-data`.

**Face detection finds nothing, ever.** The cascade files are missing:
`sudo apt install opencv-data`.

**Stream won't connect.** Start it on the robot: `cockpit`, item 7. Item 8 shows
the stream's log.

**`mosh` fails but `ssh` works.** Usually mosh missing on one end, a non-UTF-8
locale on the robot, or UDP 60000-61000 blocked.
