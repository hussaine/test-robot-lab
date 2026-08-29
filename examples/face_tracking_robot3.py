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
MAX_STEER = 30

SEND_THRESHOLD_DEG = 1.0
MAX_MISSED_FRAMES = 3
missed_frames = 0


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
            missed_frames = 0
            face = faces[0]                    # largest face = nearest person
            face_center_x = face["cx"]
            error = face_center_x - frame_center_x

            # Hardware-debug controller: no proportional steering, smoothing,
            # or command thresholding. Send this command every frame.
            if error < -DEAD_ZONE:
                region = "LEFT"
                action = "TURN LEFT"
            elif error > DEAD_ZONE:
                region = "RIGHT"
                action = "TURN RIGHT"
            else:
                region = "CENTER"
                action = "STRAIGHT"

            # Proportional controller:
            # farther from the image center -> larger steering correction
            if abs(error) <= DEAD_ZONE:
                target_angle = 0.0
            else:
                direction = 1 if error > 0 else -1

                # Remove the dead-zone portion of the error.
                effective_error = abs(error) - DEAD_ZONE

                # Maximum possible error outside the dead zone.
                usable_range = (width / 2) - DEAD_ZONE

                normalized_error = effective_error / usable_range

                target_angle = direction * normalized_error * MAX_STEER
                target_angle = max(-MAX_STEER, min(MAX_STEER, target_angle))

            # No smoothing yet.
            steering_angle = target_angle

            # A red dot makes the face centre easy to compare with the blue line.
            cv2.circle(frame, (face_center_x, face["cy"]), 6, (0, 0, 255), -1)
            cv2.putText(frame, region, (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 255, 0), 2)
            cv2.putText(frame, f"error: {error:+d} px", (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"target: {target_angle:+.1f} deg", (20, 105),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.putText(frame, f"steer: {steering_angle:+.1f} deg", (20, 140),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            missed_frames += 1
            if missed_frames <= MAX_MISSED_FRAMES:
                # Keep previous steering briefly.
                steering_angle = last_steering_angle
            else:
                steering_angle = 0
            error = None
            target_angle = 0
            #action = "STOP"
            if missed_frames <= MAX_MISSED_FRAMES:
                action = "FACE LOST - HOLD"
            else:
                action = "FACE LOST - STRAIGHT"
            cv2.putText(frame, "NO FACE", (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 0, 255), 2)
            cv2.putText(frame, "error: -- px", (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Command thresholding is deliberately disabled for this debug version.
        # Send a steering command only when the angle has changed enough.
        should_send = (
            abs(steering_angle - last_steering_angle) >= SEND_THRESHOLD_DEG
        )

        # If the face has been lost for more than the grace period,
        # force a straight command even if the difference is small.
        if missed_frames > MAX_MISSED_FRAMES and last_steering_angle != 0:
            should_send = True

        error_text = f"{error:+d}" if error is not None else "--"

        print(
            f"error={error_text} "
            f"target={target_angle:+.1f} "
            f"steer={steering_angle:+.1f} "
            f"last={last_steering_angle:+.1f} "
            f"SEND={should_send}"
        )

        if should_send:
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
