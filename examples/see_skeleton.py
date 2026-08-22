#!/usr/bin/env python3
"""Draw a skeleton on whoever is standing in front of the robot.

Run it in the VM, with your robot's number:

    python3 ~/test-robot-lab/examples/see_skeleton.py 3

Needs the pose model, once:  bash ~/test-robot-lab/setup-pose.sh
Start the camera on the robot first: `cockpit`, item 7.

Stand back far enough that most of your body is in shot -- this needs a body,
not a head and shoulders. Press q or Esc to stop.
"""

import sys

import robocam as cam

if len(sys.argv) < 2:
    sys.exit("which robot? e.g.  python3 see_skeleton.py 3")

cam.connect(sys.argv[1])

print("Looking for a person. q or Esc to stop.")

while True:
    picture = cam.getFrame()
    picture, joints = cam.getSkeleton(picture)

    # Joints that are hidden or out of shot simply aren't there, so always check
    # before using one.
    if "right_wrist" in joints and "right_shoulder" in joints:
        wrist = joints["right_wrist"]
        shoulder = joints["right_shoulder"]

        # y counts downwards from the top of the picture, so a hand held up has
        # a *smaller* y than the shoulder.
        if wrist["y"] < shoulder["y"]:
            print("right hand up!    ", end="\r")
        else:
            print("right hand down   ", end="\r")
    else:
        print(f"{len(joints)} joints found", end="\r")

    if not cam.showImage(picture):
        break

print("\nDone.")

# Things to try:
#   * print(joints) once, to see the whole dict
#   * for name in robocam.JOINTS: print(name, name in joints)
#   * measure how far apart two joints are:
#       both hands = joints["left_wrist"], joints["right_wrist"]
#   * make the robot drive when you raise a hand -- ssh into it and use roboshine
#   * watch cam.getFrameAge(): skeletons are slower than faces, and the lag shows
