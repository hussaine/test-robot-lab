#!/usr/bin/env python3
"""Decide which way a robot would turn to keep a face in the middle.

Run it in the VM, with your robot's number:

    python3 ~/test-robot-lab/examples/face_tracking.py 3

Start the camera on the robot first: `cockpit`, item 7.
This demo only sees and decides; it never moves the robot.
Press q or Esc, or close the window, to stop.
"""

import sys

import cv2

import robocam as cam


# Pixels on either side of the image centre that count as "close enough".
DEAD_ZONE = 60


if len(sys.argv) < 2:
    sys.exit("which robot? e.g.  python3 face_tracking.py 3")

cam.connect(sys.argv[1])

print("Face tracking decision demo. The robot will not move. q or Esc to stop.")

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

        if error < -DEAD_ZONE:
            region = "LEFT"
            action = "TURN LEFT"
        elif error > DEAD_ZONE:
            region = "RIGHT"
            action = "TURN RIGHT"
        else:
            region = "CENTER"
            action = "STRAIGHT"

        # A red dot makes the face centre easy to compare with the blue line.
        cv2.circle(frame, (face_center_x, face["cy"]), 6, (0, 0, 255), -1)
        cv2.putText(frame, region, (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (0, 255, 0), 2)
        cv2.putText(frame, f"error: {error:+d} px", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        action = "STOP"
        cv2.putText(frame, "NO FACE", (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (0, 0, 255), 2)
        cv2.putText(frame, "error: -- px", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.putText(frame, f"ACTION: {action}", (20, height - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    print(f"ACTION: {action:<10}", end="\r")

    if not cam.showImage(frame, "face tracking"):
        break

print("\nDone.")



curl http://localhost:8002/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.8-27b",
    "messages": [
      {
        "role": "user",
        "content": "What are famous medical VLA, give the answer in 3 to 5 sentences."
      }
    ],
    "temperature": 0.7,
    "top_p": 0.8,
    "presence_penalty": 1.5,
    "max_tokens": 300,
    "chat_template_kwargs": {
      "enable_thinking": false
    }
  }' | python3 -m json.tool
