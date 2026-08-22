#!/usr/bin/env python3
"""Look through the robot's camera. The simplest robocam script there is.

Run it in the VM, with your robot's number:

    python3 ~/test-robot-lab/examples/first_look.py 3

Start the camera on the robot first: `cockpit`, item 7.
Press q or Esc, or close the window, to stop.
"""

import sys

import robocam as cam

if len(sys.argv) < 2:
    sys.exit("which robot? e.g.  python3 first_look.py 3")

cam.connect(sys.argv[1])

print("Showing the camera. q or Esc to stop.")

while True:
    picture = cam.getFrame()

    # getFrameAge() is how old the picture already was when we got it -- the
    # honest lag between the robot and this window.
    print(f"lag {cam.getFrameAge() * 1000:5.0f} ms", end="\r")

    if not cam.showImage(picture):
        break

print("\nDone.")

# Things to try:
#   * cam.saveImage(picture, "snap.jpg") inside the loop
#   * watch the lag while you drive the robot around from the cockpit
#   * turn the robot's camera with roboshine's lookLeft() on the robot side
