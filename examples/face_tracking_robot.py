#!/usr/bin/env python3
"""Steer a robot's front wheels to keep a face in the middle.

Run it in the VM, with your robot's number:

    python3 ~/test-robot-lab/examples/face_tracking_robot.py robot-1.local

Start the camera on the robot first: `cockpit`, item 7.
The drive motors remain stopped; front wheels will steer.
Press q or Esc, or close the window, to stop.
"""

import sys

from pathlib import Path

# Allow this example to import modules from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

import robocam as cam
import robot_remote as robot


# Pixels on either side of the image centre that count as "close enough".
DEAD_ZONE = 60


if len(sys.argv) < 2:
    sys.exit("which robot? e.g.  python3 face_tracking_robot.py 3")

robot_name = sys.argv[1]
if "." not in robot_name:
    robot_name = f"robot-{robot_name}.local"

connected = False
last_steering_angle = 0

try:
    robot.connect(robot_name)
    connected = True
    print(f"Robot connected to {robot_name}")
    print(f"Robot ping: {robot.ping()}")

    cam.connect(sys.argv[1])
    print("Face tracking hardware-debug demo. "
          "The drive motors remain stopped; front wheels will steer. q or Esc to stop.")

    while True:
        frame = cam.getFrame()                 # always waits for a newest frame
        frame, faces = cam.findFaces(frame)    # boxes are drawn on this copy

        height, width = frame.shape[:2]
        frame_center_x = width // 2

        # Draw the centre line and the configurable dead-zone around it.
        cv2.line(frame, (frame_center_x, 0), (frame_center_x, height),
                 (255, 255, 0), 2)
        cv2.line(frame, (frame_center_x - DEAD_ZONE, 0),
                 (frame_center_x - DEAD_ZONE, height), (0, 255, 255), 1)
        cv2.line(frame, (frame_center_x + DEAD_ZONE, 0),
                 (frame_center_x + DEAD_ZONE, height), (0, 255, 255), 1)

        if faces:
            face = faces[0]                    # largest face = nearest person
            face_center_x = face["cx"]
            error = face_center_x - frame_center_x

            # Hardware-debug controller: no proportional steering, smoothing,
            # or command thresholding. Send this command every frame.
            if error < -DEAD_ZONE:
                steering_angle = -20
                region = "LEFT"
                action = "TURN LEFT"
            elif error > DEAD_ZONE:
                steering_angle = 20
                region = "RIGHT"
                action = "TURN RIGHT"
            else:
                steering_angle = 0
                region = "CENTER"
                action = "STRAIGHT"

            target_angle = steering_angle

            # A red dot makes the face centre easy to compare with the blue line.
            cv2.circle(frame, (face_center_x, face["cy"]), 6, (0, 0, 255), -1)
            cv2.putText(frame, region, (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 255, 0), 2)
            cv2.putText(frame, f"error: {error:+d} px", (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            error = None
            target_angle = 0
            steering_angle = 0
            action = "STOP"
            cv2.putText(frame, "NO FACE", (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 0, 255), 2)
            cv2.putText(frame, "error: -- px", (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Command thresholding is deliberately disabled for this debug version.
        should_send = True
        error_text = f"{error:+d}" if error is not None else "--"
        print(f"error={error_text} target={target_angle:+.1f} "
              f"smooth={steering_angle:+.1f} last={last_steering_angle:+.1f} "
              f"SEND={should_send}")
        robot.steer(steering_angle)
        print(f"STEER {steering_angle:+.1f}")
        last_steering_angle = steering_angle

        cv2.putText(frame, f"ACTION: {action}", (20, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        if not cam.showImage(frame, "face tracking"):
            break
finally:
    if connected:
        try:
            robot.steer(0)
        finally:
            robot.close()

print("Done.")
