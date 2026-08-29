#!/usr/bin/env python3
"""Follow the nearest face while keeping a safe ultrasonic distance.

Run it in the VM, with your robot's number:

    python3 ~/test-robot-lab/examples/follow_me.py robot-3.local

Start the camera on the robot first: `cockpit`, item 7.
Press q or Esc, or close the window, to stop safely.
"""

import sys
from pathlib import Path

# Allow this example to import modules from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

import robocam as cam
import robot_remote as robot


DEAD_ZONE = 60
MAX_STEER = 30
MAX_MISSED_FRAMES = 3
SEND_THRESHOLD_DEG = 1.0

STRAIGHT_SPEED = 20
TURN_SPEED = 12

# Physical calibration: use a small negative value if the robot drifts right.
STEERING_TRIM_DEG = -2.0

EMERGENCY_DISTANCE_CM = 25
FOLLOW_DISTANCE_CM = 50


if len(sys.argv) < 2:
    sys.exit("which robot? e.g.  python3 follow_me.py 3")

robot_name = sys.argv[1]
if "." not in robot_name:
    robot_name = f"robot-{robot_name}.local"

connected = False
last_steering_angle = 0.0
drive_state = "STOP"
missed_frames = 0


def stop_drive():
    """Stop only when the drive state changes.

    robot.stop() also straightens the wheels, so remember that before a
    following steering command decides whether it needs to be sent.
    """
    global drive_state, last_steering_angle

    if drive_state != "STOP":
        robot.stop()
        drive_state = "STOP"
        last_steering_angle = 0.0
        print("DRIVE STOP")


def drive_forward(speed):
    """Move forward at the requested speed only when the state changes."""
    global drive_state

    forward_state = f"FORWARD {speed}"
    if drive_state != forward_state:
        robot.forward(speed)
        drive_state = forward_state
        print(f"DRIVE {forward_state}")


def send_steering(steering_angle, force=False):
    """Send steering with physical straight-line calibration."""
    global last_steering_angle

    command_angle = steering_angle + STEERING_TRIM_DEG
    command_angle = max(-MAX_STEER, min(MAX_STEER, command_angle))

    if force or abs(command_angle - last_steering_angle) >= SEND_THRESHOLD_DEG:
        robot.steer(command_angle)
        last_steering_angle = command_angle
        print(
            f"STEER target={steering_angle:+.1f} "
            f"command={command_angle:+.1f} deg"
        )


try:
    robot.connect(robot_name)
    connected = True
    print(f"Robot connected to {robot_name}")

    cam.connect(sys.argv[1])
    print("Follow-me demo started. Press q or Esc to stop.")

    while True:
        frame = cam.getFrame()
        frame = cv2.flip(frame, 1)
        frame, faces = cam.findFaces(frame)  # Face boxes are drawn on this copy.
        distance_cm = robot.distance()

        height, width = frame.shape[:2]
        frame_center_x = width // 2
        cv2.line(frame, (frame_center_x, 0), (frame_center_x, height),
                 (255, 255, 0), 2)
        cv2.line(frame, (frame_center_x - DEAD_ZONE, 0),
                 (frame_center_x - DEAD_ZONE, height), (0, 255, 255), 1)
        cv2.line(frame, (frame_center_x + DEAD_ZONE, 0),
                 (frame_center_x + DEAD_ZONE, height), (0, 255, 255), 1)

        valid_distance = distance_cm > 0
        error = None

        if not faces:
            # A lost face always stops the drive motors right away.
            drive_speed = 0
            held_steering_angle = last_steering_angle
            stop_drive()
            missed_frames += 1
            region = "LOST"
            if missed_frames <= MAX_MISSED_FRAMES:
                steering_angle = held_steering_angle
                action = "FACE LOST - HOLD"
            else:
                steering_angle = 0.0
                action = "FACE LOST - STRAIGHT"
        else:
            missed_frames = 0
            face = faces[0]  # Largest face = nearest person.
            face_center_x = face["cx"]
            error = face_center_x - frame_center_x

            if error < -DEAD_ZONE:
                region = "LEFT"
            elif error > DEAD_ZONE:
                region = "RIGHT"
            else:
                region = "CENTER"

            # Same proportional steering calculation as face_tracking_robot3.py.
            if abs(error) <= DEAD_ZONE:
                target_angle = 0.0
            else:
                direction = 1 if error > 0 else -1
                effective_error = abs(error) - DEAD_ZONE
                usable_range = (width / 2) - DEAD_ZONE
                normalized_error = effective_error / usable_range
                #target_angle = direction * normalized_error * MAX_STEER
                target_angle = -direction * normalized_error * MAX_STEER
                target_angle = max(-MAX_STEER, min(MAX_STEER, target_angle))

            steering_angle = target_angle
            cv2.circle(frame, (face_center_x, face["cy"]), 6, (0, 0, 255), -1)

            if not valid_distance:
                stop_drive()
                action = "INVALID DISTANCE - STOP"
            elif distance_cm < EMERGENCY_DISTANCE_CM:
                stop_drive()
                action = "EMERGENCY STOP"
            elif abs(error) > DEAD_ZONE:
                # A car-style robot must move in order to turn.
                # Use a slower speed while making a steering correction.
                drive_forward(TURN_SPEED)
                action = f"FOLLOW {region}"
            elif distance_cm > FOLLOW_DISTANCE_CM:
                drive_forward(STRAIGHT_SPEED)
                action = "FOLLOW STRAIGHT"
            else:
                stop_drive()
                action = "HOLD DISTANCE"

        # Stopping may have straightened the wheels, so send the desired angle
        # afterward. A long face loss must explicitly return to straight ahead.
        force_straight = (
            not faces
            and missed_frames > MAX_MISSED_FRAMES
            and last_steering_angle != 0
        )
        send_steering(steering_angle, force=force_straight)

        error_text = f"{error:+d} px" if error is not None else "-- px"
        distance_text = f"{distance_cm:.1f} cm" if valid_distance else "unknown"
        drive_text = drive_state
        cv2.putText(frame, f"FACE: {region}", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(frame, f"error: {error_text}", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"steer: {steering_angle:+.1f} deg", (20, 105),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"distance: {distance_text}", (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"DRIVE: {drive_text}", (20, 175),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"ACTION: {action}", (20, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        if not cam.showImage(frame, "follow me"):
            break
except KeyboardInterrupt:
    print("Stopped with Ctrl-C")
finally:
    if connected:
        try:
            robot.stop()
        finally:
            try:
                robot.steer(0)
            finally:
                robot.close()

print("Done.")
