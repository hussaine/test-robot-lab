#!/usr/bin/env python3
"""Test remote steering without driving the robot.

Run this in the VM, with your robot's number or hostname:

    python3 ~/test-robot-lab/examples/test_remote_steering.py 3

First copy pi/robot_server.py to the Pi and run it there. This script changes
only the front-wheel angle; it never tells the motors to drive.
"""

import sys
import time
from pathlib import Path

# This lets the example find robot_remote.py when run by its full path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import robot_remote as robot


if len(sys.argv) < 2:
    sys.exit("which robot? e.g.  python3 test_remote_steering.py 3")

robot_name = sys.argv[1]
if "." not in robot_name:
    robot_name = f"robot-{robot_name}.local"

connected = False

try:
    robot.connect(robot_name)
    connected = True
    print("Connected:", robot.ping())

    print("Steering left")
    robot.steer(-20)
    time.sleep(1)

    print("Steering straight")
    robot.steer(0)
    time.sleep(1)

    print("Steering right")
    robot.steer(20)
    time.sleep(1)

finally:
    # This test never drives the motors. Stop is still the safe final command.
    if connected:
        try:
            robot.steer(0)
            robot.stop()
        finally:
            robot.close()

print("Done.")
