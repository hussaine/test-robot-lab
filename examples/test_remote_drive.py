#!/usr/bin/env python3
"""Briefly test safe remote forward driving; it never drives in reverse."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import robot_remote as robot


if len(sys.argv) < 2:
    sys.exit("which robot? e.g.  python3 test_remote_drive.py robot-1.local")

robot_name = sys.argv[1]
if "." not in robot_name:
    robot_name = f"robot-{robot_name}.local"

connected = False
try:
    robot.connect(robot_name)
    connected = True
    print("Connected:", robot.ping())
    print(f"Distance: {robot.distance():.1f} cm")
    robot.steer(0)
    print("ROBOT WILL MOVE FORWARD")
    robot.forward(20)
    time.sleep(0.75)
    robot.stop()
    print(f"Distance: {robot.distance():.1f} cm")
finally:
    if connected:
        try:
            robot.stop()
        except Exception:
            pass
        #finally:
        try:
            robot.steer(0)
        except Exception:
            pass
            #finally:
        robot.close()
