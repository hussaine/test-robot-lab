#!/usr/bin/env python3
"""Steer a robot with simple raised-hand gestures.

Run it in the VM, with your robot's number:

    python3 ~/test-robot-lab/examples/gesture_control.py robot-3.local

Start the camera on the robot first: `cockpit`, item 7. Pose detection needs
the one-time setup command: `bash ~/test-robot-lab/setup-pose.sh`.
Press q or Esc, or close the window, to stop safely.
"""

import sys
from pathlib import Path

# Allow this example to import modules from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

import robocam as cam
import robot_remote as robot


# Seeing the same gesture for three frames makes pose tracking less jumpy.
STABLE_FRAMES = 3

STRAIGHT_SPEED = 15
TURN_SPEED = 12

GESTURE_ANGLES = {
    "LEFT": -20,       # robot_remote: negative steering is left.
    "RIGHT": 20,       # robot_remote: positive steering is right.
    "STOP": 0,
    "STRAIGHT": 0,
}


if len(sys.argv) < 2:
    sys.exit("which robot? e.g.  python3 gesture_control.py 3")

robot_name = sys.argv[1]
if "." not in robot_name:
    robot_name = f"robot-{robot_name}.local"

connected = False
last_command_gesture = "STOP"
candidate_gesture = None
candidate_frames = 0


def gesture_from_joints(joints):
    """Return a gesture when all four joints needed for it are visible."""
    required_joints = (
        "left_wrist", "left_shoulder", "right_wrist", "right_shoulder",
    )
    if not all(joint in joints for joint in required_joints):
        return None

    # Image y values get smaller higher in the picture.
    left_raised = joints["left_wrist"]["y"] < joints["left_shoulder"]["y"]
    right_raised = joints["right_wrist"]["y"] < joints["right_shoulder"]["y"]

    if left_raised and right_raised:
        return "STOP"
    if left_raised:
        return "LEFT"
    if right_raised:
        return "RIGHT"
    return "STRAIGHT"


def action_text(gesture):
    """Describe the robot action in classroom-friendly words."""
    if gesture == "LEFT":
        return "TURN LEFT"
    if gesture == "RIGHT":
        return "TURN RIGHT"
    if gesture == "STOP":
        return "STOP"
    return "FORWARD"

def apply_gesture(gesture):
    """Turn a stable gesture into steering + movement."""
    if gesture == "LEFT":
        robot.steer(GESTURE_ANGLES["LEFT"])
        robot.forward(TURN_SPEED)

    elif gesture == "RIGHT":
        robot.steer(GESTURE_ANGLES["RIGHT"])
        robot.forward(TURN_SPEED)

    elif gesture == "STRAIGHT":
        robot.steer(0)
        robot.forward(STRAIGHT_SPEED)

    elif gesture == "STOP":
        robot.stop()
        robot.steer(0)


try:
    robot.connect(robot_name)
    connected = True
    robot.stop()  # Safety at startup; it also makes sure the wheels are straight.
    print(f"Robot connected to {robot_name}")

    cam.connect(sys.argv[1])
    print("Gesture steering demo started. No rear motors are used. q or Esc to stop.")

    while True:
        frame = cam.getFrame()
        frame = cv2.flip(frame, 1)
        frame, joints = cam.getSkeleton(frame)  # This also draws the skeleton.
        observed_gesture = gesture_from_joints(joints)

        if observed_gesture is None:
            # Losing the person is an immediate safety stop.
            candidate_gesture = None
            candidate_frames = 0

            if last_command_gesture != "STOP":
                robot.stop()
                robot.steer(0)
                last_command_gesture = "STOP"
                print("GESTURE lost: STOP")

            gesture_display = "NO PERSON"
            action_display = "STOP"
        else:
            if observed_gesture == candidate_gesture:
                candidate_frames += 1
            else:
                candidate_gesture = observed_gesture
                candidate_frames = 1

            if (
                candidate_frames >= STABLE_FRAMES
                and observed_gesture != last_command_gesture
            ):
                apply_gesture(observed_gesture)
                last_command_gesture = observed_gesture
                print(f"GESTURE {observed_gesture}: {action_text(observed_gesture)}")

            gesture_display = observed_gesture
            if candidate_frames < STABLE_FRAMES:
                action_display = f"WAIT ({candidate_frames}/{STABLE_FRAMES})"
            else:
                action_display = action_text(last_command_gesture)

        # Keep the status out of the way of the person in a small camera frame.
        #cv2.rectangle(frame, (8, 8), (285, 76), (0, 0, 0), -1)
        cv2.putText(frame, f"GESTURE: {gesture_display}", (16, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1,
                    cv2.LINE_AA)
        cv2.putText(frame, f"ACTION: {action_display}", (16, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1,
                    cv2.LINE_AA)

        if not cam.showImage(frame, "gesture control"):
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
