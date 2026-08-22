#!/usr/bin/env python3
"""Find faces in the robot's camera stream.

Run it in the VM, with your robot's number:

    python3 ~/test-robot-lab/examples/see_faces.py 3

Start the camera on the robot first: `cockpit`, item 7.
Press q or Esc, or close the window, to stop.
"""

import sys

import robocam as cam

if len(sys.argv) < 2:
    sys.exit("which robot? e.g.  python3 see_faces.py 3")

cam.connect(sys.argv[1])

print("Looking for faces. q or Esc to stop.")

while True:
    picture = cam.getFrame()

    # findFaces gives back a copy with boxes drawn on it, plus the faces
    # themselves -- biggest first, so faces[0] is the nearest person.
    picture, faces = cam.findFaces(picture)

    if faces:
        nearest = faces[0]
        middle = picture.shape[1] // 2          # how wide the picture is, halved

        if nearest["cx"] < middle - 60:
            print("face on the left ", end="\r")
        elif nearest["cx"] > middle + 60:
            print("face on the right", end="\r")
        else:
            print("face in the middle", end="\r")

    if not cam.showImage(picture):
        break

print("\nDone.")

# Things to try:
#   * print(len(faces)) to count everyone in shot
#   * save a picture when a face shows up:
#       if faces: cam.saveImage(picture, "found.jpg")
#   * turn the robot's camera towards the face, using roboshine on the robot
#   * nearest["size"] gets bigger as someone walks closer -- print it and see
