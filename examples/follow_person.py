#!/usr/bin/env python3
"""Follow the nearest detected person while keeping a safe distance.

Run it on the laptop, with your robot's number:

    python3 ~/test-robot-lab/examples/follow_person.py robot-3.local

Start the camera on the robot first: `cockpit`, item 7.
The first run downloads the selected YOLO model if it is not already cached.
Press q or Esc, or close the window, to stop safely.
"""

import sys
import time
from pathlib import Path

# Allow this example to import modules from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
from ultralytics import YOLO

import robocam as cam
import robot_remote as robot


# YOLO11 nano is small enough for real-time CPU inference on a MacBook.
MODEL_NAME = "yolo11n.pt"
PERSON_CLASS_ID = 0  # COCO's class ID for person.

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
    sys.exit("which robot? e.g.  python3 follow_person.py 3")

robot_name = sys.argv[1]
if "." not in robot_name:
    robot_name = f"robot-{robot_name}.local"

connected = False
last_steering_angle = 0.0
drive_state = "STOP"
missed_frames = 0


def stop_drive():
    """Stop only when the drive state changes."""
    global drive_state, last_steering_angle

    if drive_state != "STOP":
        robot.stop()
        drive_state = "STOP"
        # robot.stop() also straightens the wheels.
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


# Load the model on the laptop before connecting to the robot. This keeps a
# model-download or model-loading failure away from the drive hardware.
print(f"Loading person detector: {MODEL_NAME}")
model = YOLO(MODEL_NAME)

try:
    robot.connect(robot_name)
    connected = True
    print(f"Robot connected to {robot_name}")

    cam.connect(sys.argv[1])
    print("Person-following demo started. Press q or Esc to stop.")

    while True:
        frame = cam.getFrame()
        frame = cv2.flip(frame, 1)
        distance_cm = robot.distance()

        # Inference runs here on the laptop. Restrict YOLO to COCO's person
        # class, then choose the largest detected person as the target.
        inference_started = time.perf_counter()
        result = model(frame, classes=[PERSON_CLASS_ID], verbose=False)[0]
        inference_seconds = time.perf_counter() - inference_started
        inference_fps = 1 / inference_seconds if inference_seconds else 0
        people = []
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
            confidence = float(box.conf[0].item())
            area = (x2 - x1) * (y2 - y1)
            people.append((area, x1, y1, x2, y2, confidence))

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

        if not people:
            # A lost person always stops the drive motors right away.
            held_steering_angle = last_steering_angle
            stop_drive()
            missed_frames += 1
            region = "LOST"
            if missed_frames <= MAX_MISSED_FRAMES:
                steering_angle = held_steering_angle
                action = "PERSON LOST - HOLD"
            else:
                steering_angle = 0.0
                action = "PERSON LOST - STRAIGHT"
        else:
            missed_frames = 0
            _, x1, y1, x2, y2, confidence = max(people, key=lambda person: person[0])
            person_center_x = round((x1 + x2) / 2)
            person_center_y = round((y1 + y2) / 2)
            error = person_center_x - frame_center_x

            cv2.rectangle(frame, (round(x1), round(y1)), (round(x2), round(y2)),
                          (0, 255, 0), 4)
            cv2.circle(frame, (person_center_x, person_center_y), 10,
                       (0, 0, 255), -1)
            cv2.circle(frame, (person_center_x, person_center_y), 12,
                       (255, 255, 255), 2)

            if error < -DEAD_ZONE:
                region = "LEFT"
            elif error > DEAD_ZONE:
                region = "RIGHT"
            else:
                region = "CENTER"

            # Same proportional steering controller as follow_me2.py.
            if abs(error) <= DEAD_ZONE:
                target_angle = 0.0
            else:
                direction = 1 if error > 0 else -1
                effective_error = abs(error) - DEAD_ZONE
                usable_range = (width / 2) - DEAD_ZONE
                normalized_error = effective_error / usable_range
                target_angle = -direction * normalized_error * MAX_STEER
                target_angle = max(-MAX_STEER, min(MAX_STEER, target_angle))

            steering_angle = target_angle

            if not valid_distance:
                stop_drive()
                action = "INVALID DISTANCE - STOP"
            elif distance_cm < EMERGENCY_DISTANCE_CM:
                stop_drive()
                action = "EMERGENCY STOP"
            elif abs(error) > DEAD_ZONE:
                # A car-style robot must move in order to turn.
                drive_forward(TURN_SPEED)
                action = f"FOLLOW {region}"
            elif distance_cm > FOLLOW_DISTANCE_CM:
                drive_forward(STRAIGHT_SPEED)
                action = "FOLLOW STRAIGHT"
            else:
                stop_drive()
                action = "HOLD DISTANCE"

        force_straight = (
            not people
            and missed_frames > MAX_MISSED_FRAMES
            and last_steering_angle != 0
        )
        send_steering(steering_angle, force=force_straight)

        error_text = f"{error:+d} px" if error is not None else "-- px"
        confidence_text = f"{confidence:.2f}" if people else "--"
        distance_text = f"{distance_cm:.0f} cm" if valid_distance else "unknown"

        # Large, compact readouts make the controller state visible on a projector.
        overlay_lines = [
            f"PERSON  conf: {confidence_text}",
            f"ERROR   {error_text}",
            f"STEER   {steering_angle:+.1f} deg",
            f"DIST    {distance_text}",
            f"ACTION  {action}",
        ]
        for index, line in enumerate(overlay_lines):
            y = 42 + index * 42
            cv2.putText(frame, line, (24, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.95, (255, 255, 255), 3, cv2.LINE_AA)

        cv2.putText(frame, f"FPS {inference_fps:.1f}", (width - 150, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2,
                    cv2.LINE_AA)

        if not cam.showImage(frame, "follow person"):
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
