# Physical AI & Robotics Bootcamp — Student Setup

Please complete this setup **before the lab session**.

The lab uses a Raspberry Pi based robot, but most computer vision processing runs on your Ubuntu computer/VM. During class, your computer will communicate with an assigned robot over Wi-Fi.

---

## 1. Requirements

You should have:

- Ubuntu 24.04 VM or Ubuntu computer
- Internet access for initial setup
- Git
- Python 3
- A graphical desktop environment

You do **not** need access to a robot while completing the initial setup.

---

## 2. Clone the Lab Repository

Open a terminal.

Install Git if necessary:

```bash
sudo apt update
sudo apt install -y git
```

Clone the repository:

```bash
git clone https://github.com/sjaraza/test-robot-lab.git ~/test-robot-lab
```

Enter the repository:

```bash
cd ~/test-robot-lab
```

---

## 3. Install the Lab Environment

Run:

```bash
bash ~/test-robot-lab/setup-vm.sh
```

This installs the main tools used in the lab, including:

- OpenCV
- NumPy
- Haar cascade data
- SSH tools
- FFmpeg
- networking utilities
- robot camera support

The lab intentionally uses Ubuntu system packages where possible.

After setup finishes, **open a new terminal**.

---

## 4. Verify the Camera Library

Run:

```bash
python3 -c "import robocam; robocam.showHelp()"
```

You should see the `robocam` help output.

If you receive:

```text
ModuleNotFoundError: No module named 'robocam'
```

run:

```bash
bash ~/test-robot-lab/install.sh
```

and open a new terminal.

---

## 5. Install Pose / Gesture Support

Some demos use human pose estimation.

Run:

```bash
bash ~/test-robot-lab/setup-pose.sh
```

If your instructor tells you pose support is optional for your machine, you may skip this step.

---

# During Class

## 6. Connect to the Class Wi-Fi

Your computer and robot must be connected to the **same network**.

Each robot has a hostname such as:

```text
robot-1.local
robot-2.local
robot-3.local
```

Your instructor will tell you which robot to use.

---

## 7. Check Robot Connectivity

For robot 1:

```bash
ping robot-1.local
```

Replace `1` with your assigned robot number.

You can also connect using SSH:

```bash
ssh robot@robot-1.local
```

The instructor will provide the robot password if needed.

---

## 8. Start the Robot Camera

SSH to your robot:

```bash
ssh robot@robot-1.local
```

Then run:

```bash
cockpit
```

You will see a menu similar to:

```text
1   Drive with arrow keys
2   Measure distance
3   Drive for a set time
4   Steer to an angle
5   Point the camera
6   Read line sensors
7   Camera stream on / off
8   Camera logs
9   Stop everything
```

Choose:

```text
7
```

to start the camera stream.

Confirm that the camera is shown as live.

You may then quit `cockpit`; the camera stream will remain running.

---

## 9. Test the Camera From Your Computer

From your Ubuntu machine:

```bash
python3 ~/test-robot-lab/examples/first_look.py 1
```

Replace `1` with your robot number.

You can also try face detection:

```bash
python3 ~/test-robot-lab/examples/see_faces.py 1
```

or:

```bash
python3 ~/test-robot-lab/cvclient.py 1 --detect faces
```

Press `q` or `Esc` to close the camera window.

---

# Important Architecture

The Raspberry Pi on the robot is intentionally lightweight.

The architecture is approximately:

```text
ROBOT                               YOUR COMPUTER

Camera
  │
  ↓
Raspberry Pi
capture + encode
  │
  │ Wi-Fi video stream
  └──────────────────────────────→ OpenCV / AI
                                     │
                                     ↓
                                  Perception
```

Most computer vision processing happens on your computer rather than on the Raspberry Pi.

This lets us experiment with more interesting AI models while still using a small robot.

---

# Before Class Checklist

Please verify:

```text
[ ] Ubuntu / VM starts successfully
[ ] Git repository has been cloned
[ ] setup-vm.sh completes successfully
[ ] `import robocam` works
[ ] setup-pose.sh has been attempted/completed if requested
```

You do **not** need to be able to connect to a robot from home.

Robot access and networking will be provided during the class.

---

# Updating the Repository

Before class, update your code:

```bash
cd ~/test-robot-lab
git pull
```

If the lab setup installed the `update` helper, you may instead run:

```bash
update
```
