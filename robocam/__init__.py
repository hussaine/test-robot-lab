"""robocam -- see through your robot's camera from your own Python scripts.

Runs in the VM, not on the robot. The robot only films; every bit of the seeing
happens here, where there is a real processor.

    import robocam as cam

    cam.connect(3)                          # your robot's number or letter
    picture = cam.getFrame()
    picture, faces = cam.findFaces(picture)
    print(len(faces), "faces")
    cam.showImage(picture)

Type cam.showHelp() to see everything available.

Before any of this works, start the camera on the robot: `cockpit`, item 7.

Notes for anyone reading the code rather than using it:

* Nothing is imported until it is needed -- not OpenCV, not the pose model. So
  showHelp() works on a machine with nothing installed, and a typo in a script
  reports the typo rather than a missing library.
* getFrame() always returns the *newest* frame and never the same one twice. It
  waits for a fresh one, which paces a student's loop to the stream by itself.
  Old frames are dropped rather than queued: a queue would mean their picture
  drifts further behind reality the slower their code is.
* findFaces() and getSkeleton() draw on a *copy* and hand it back, so the clean
  frame is still there to use. That is why they return two things.
* The joints from getSkeleton() are the same 13 names whatever is doing the
  detecting underneath, so scripts keep working if the backend changes.
* The stream is closed when the script ends, however it ends.
"""

import atexit
import time

from . import _pose
from ._stream import DEFAULT_PORT, Stream, resolve_host

__version__ = "0.1"

__all__ = [
    "connect", "disconnect", "isConnected",
    "getFrame", "getFrameAge",
    "findFaces", "getSkeleton",
    "showImage", "saveImage", "closeWindows",
    "wait", "showHelp",
    "JOINTS",
]

JOINTS = _pose.JOINTS               # the joint names getSkeleton() can return

# How long getFrame() waits for a frame before giving up. Generous, because the
# very first frame also has to travel over a busy 2.4GHz radio.
FRAME_TIMEOUT = 5.0

_stream = None
_last_age = 0.0
_cascade = None
_windows = set()


# ---------------------------------------------------------------------------
# lazily-loaded libraries
# ---------------------------------------------------------------------------

def _cv():
    """OpenCV, imported on first use."""
    try:
        import cv2                                          # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            f"OpenCV isn't installed ({exc}).\n"
            "In the VM, run: sudo apt install python3-opencv opencv-data"
        ) from exc
    return cv2


def _np():
    try:
        import numpy                                        # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            f"numpy isn't installed ({exc}).\n"
            "In the VM, run: sudo apt install python3-numpy"
        ) from exc
    return numpy


def _check_number(value, name, low, high):
    """Validate before anything else happens.

    A typo should say what the typo was, rather than failing later inside a
    library with a message about arrays.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} should be a number, not {type(value).__name__}")
    if not low <= value <= high:
        raise ValueError(f"{name} should be between {low} and {high}, not {value}")
    return value


def _check_image(image, where):
    """Catch the common mistake of passing something that isn't a picture."""
    if image is None:
        raise ValueError(
            f"{where} was given nothing. Did getFrame() return None because the "
            "stream stopped?")
    if not hasattr(image, "shape") or len(getattr(image, "shape", ())) < 2:
        raise TypeError(
            f"{where} needs a picture from getFrame(), not "
            f"{type(image).__name__}")
    return image


# ---------------------------------------------------------------------------
# connecting
# ---------------------------------------------------------------------------

def connect(robot, port=DEFAULT_PORT):
    """Connect to your robot's camera. Do this once, at the top of your script.

        connect(3)                  robot-3
        connect('A')                robot-A
        connect('robot-3.local')    a full name also works

    Returns immediately -- the first frame arrives a moment later, and getFrame()
    waits for it. Start the camera on the robot first: `cockpit`, item 7.
    """
    global _stream, _last_age

    host = resolve_host(robot)
    _check_number(port, "port", 1, 65535)

    if _stream is not None:
        if _stream.host == host and _stream.port == port:
            return host                     # already watching this robot
        disconnect()

    _last_age = 0.0
    _stream = Stream(host, int(port))
    print(f"robocam {__version__}: watching {host}")
    return host


def isConnected():
    """True once connect() has been called."""
    return _stream is not None


def disconnect():
    """Stop reading the stream. Called for you when your script ends."""
    global _stream
    if _stream is not None:
        _stream.close()
        _stream = None


def _require_stream():
    if _stream is None:
        raise RuntimeError(
            "not connected to a robot yet. Put this at the top of your script:\n"
            "    cam.connect(3)        # your robot's number or letter")
    return _stream


# ---------------------------------------------------------------------------
# getting pictures
# ---------------------------------------------------------------------------

def getFrame(timeout=FRAME_TIMEOUT):
    """The newest picture from the robot's camera.

        picture = getFrame()

    Waits for a frame that you haven't already seen, so a loop like

        while True:
            picture = getFrame()
            ...

    runs at the speed of the stream by itself -- no wait() needed.

    Raises a RuntimeError if the stream can't be reached, which nearly always
    means the camera isn't running on the robot yet (`cockpit`, item 7).
    """
    global _last_age
    _check_number(timeout, "timeout", 0, 600)
    stream = _require_stream()

    jpeg, age = stream.next_jpeg(timeout)

    if jpeg is None:
        if stream.error is not None:
            raise RuntimeError(
                f"can't read the camera stream at {stream.url}\n"
                f"    ({type(stream.error).__name__}: {stream.error})\n"
                "  * is the camera running on the robot? cockpit, item 7\n"
                "  * can you reach the robot at all? try: "
                f"ping {stream.host}\n"
                "  * if the name won't resolve, the VM's network adapter needs "
                "to be Bridged, not NAT")
        raise RuntimeError(
            f"no frame arrived from {stream.host} within {timeout:g}s, "
            f"though the connection is open ({stream.frames_seen} frames so "
            "far). Is the camera still running on the robot?")

    cv2, numpy = _cv(), _np()
    picture = cv2.imdecode(numpy.frombuffer(jpeg, numpy.uint8),
                           cv2.IMREAD_COLOR)
    if picture is None:
        raise RuntimeError("a frame arrived but wasn't a readable JPEG")

    _last_age = age
    return picture


def getFrameAge():
    """How old the last getFrame() picture already was, in seconds.

    This is the honest lag between the robot's camera and your script. If it
    climbs, either the network is busy or your code is slower than the stream --
    lower the robot's frame rate rather than letting the lag build up.
    """
    return round(_last_age, 3)


# ---------------------------------------------------------------------------
# finding things
# ---------------------------------------------------------------------------

def _face_cascade():
    """The face detector, found once.

    The pip wheels bundle the cascade XML files and expose them through
    cv2.data; Ubuntu's python3-opencv has no cv2.data at all and ships them in
    /usr/share/opencv4/haarcascades via the separate opencv-data package. Look in
    both places -- and check the classifier actually loaded, because OpenCV is
    happy to return an empty one that then finds nothing, for ever, silently.
    """
    global _cascade
    if _cascade is not None:
        return _cascade

    import glob                                             # noqa: PLC0415
    import os                                               # noqa: PLC0415

    cv2 = _cv()
    name = "haarcascade_frontalface_default.xml"
    candidates = []
    if hasattr(cv2, "data"):
        candidates.append(os.path.join(cv2.data.haarcascades, name))
    candidates += sorted(glob.glob(f"/usr/share/opencv*/haarcascades/{name}"))

    for path in candidates:
        if os.path.isfile(path):
            classifier = cv2.CascadeClassifier(path)
            if not classifier.empty():
                _cascade = classifier
                return _cascade

    raise RuntimeError(
        f"couldn't find {name}, so faces can't be detected.\n"
        "In the VM, run: sudo apt install opencv-data\n"
        "(apt's OpenCV doesn't include the cascade files the way pip's does)")


def findFaces(picture, minSize=24):
    """Find faces. Returns the picture with boxes drawn on, and the faces.

        picture, faces = findFaces(picture)

        for face in faces:
            print(face["cx"], face["cy"])       # middle of the face

    Each face is a dict:

        x, y        top-left corner, in pixels
        width       how wide
        height      how tall
        cx, cy      the middle -- the useful one for aiming
        size        width * height, so the biggest face is the closest

    Faces are sorted biggest first, so faces[0] is whoever is nearest. An empty
    list means nobody was found: side-on faces and faces in shadow are missed
    often, which is a limit of the detector rather than a mistake in your code.
    """
    _check_image(picture, "findFaces()")
    _check_number(minSize, "minSize", 4, 400)

    cv2 = _cv()
    cascade = _face_cascade()

    grey = cv2.cvtColor(picture, cv2.COLOR_BGR2GRAY)
    # equalizeHist evens out the brightness, which matters a lot here: the
    # robot's camera adjusts its own exposure as it drives and faces slide in and
    # out of detection without it.
    grey = cv2.equalizeHist(grey)
    found = cascade.detectMultiScale(grey, scaleFactor=1.2, minNeighbors=4,
                                     minSize=(int(minSize), int(minSize)))

    drawn = picture.copy()
    faces = []
    for (x, y, width, height) in found:
        cv2.rectangle(drawn, (x, y), (x + width, y + height), (0, 255, 0), 2)
        centre = (int(x + width // 2), int(y + height // 2))
        cv2.circle(drawn, centre, 3, (0, 255, 0), -1)
        faces.append({
            "x": int(x), "y": int(y),
            "width": int(width), "height": int(height),
            "cx": centre[0], "cy": centre[1],
            "size": int(width) * int(height),
        })

    faces.sort(key=lambda face: face["size"], reverse=True)
    return drawn, faces


def getSkeleton(picture):
    """Find a person's body joints. Returns the picture with the skeleton drawn
    on it, and the joints.

        picture, joints = getSkeleton(picture)

        if "left_wrist" in joints:
            print(joints["left_wrist"]["x"], joints["left_wrist"]["y"])

    `joints` is a dict keyed by name, so you can ask for the one you want and
    check whether it was found. Each entry has x, y (pixels) and score (0 to 1,
    how sure it is). Joints that are hidden or out of shot are simply absent --
    check with `in` before using one.

    The names, all 13 of them, are in robocam.JOINTS:

        nose
        left_shoulder  right_shoulder
        left_elbow     right_elbow
        left_wrist     right_wrist
        left_hip       right_hip
        left_knee      right_knee
        left_ankle     right_ankle

    One person at a time -- whoever the detector locks on to. An empty dict means
    no person was found: it needs most of a body in shot, so a head-and-shoulders
    view usually finds nothing.

    Slower than findFaces(). If your lag climbs, look at getFrameAge() and drop
    the robot's frame rate.
    """
    _check_image(picture, "getSkeleton()")
    cv2 = _cv()

    joints = _pose.backend(cv2).find_points(picture, cv2)
    drawn = picture.copy()

    # Bones first, so the joint dots sit on top of the lines.
    for start, end in _pose.BONES:
        if start in joints and end in joints:
            cv2.line(drawn,
                     (joints[start]["x"], joints[start]["y"]),
                     (joints[end]["x"], joints[end]["y"]),
                     (255, 200, 0), 2)

    for name, point in joints.items():
        cv2.circle(drawn, (point["x"], point["y"]), 4, (0, 0, 255), -1)

    return drawn, joints


# ---------------------------------------------------------------------------
# showing and saving
# ---------------------------------------------------------------------------

def showImage(picture, title="robocam"):
    """Show a picture in a window. Returns False when you want to stop.

        while cam.showImage(cam.getFrame()):
            pass

    Pressing q or Esc, or closing the window, makes it return False -- so a
    `while` loop like the one above ends when the student expects it to, without
    needing Ctrl-C.
    """
    _check_image(picture, "showImage()")
    cv2 = _cv()

    _windows.add(title)
    cv2.imshow(title, picture)

    # A 1ms wait is what actually draws the window and collects key presses;
    # without it the window appears grey and never updates.
    key = cv2.waitKey(1) & 0xFF
    if key in (ord("q"), 27):               # q or Esc
        return False

    try:
        if cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
            return False                    # the student closed the window
    except cv2.error:
        return False                        # window is already gone

    return True


def closeWindows():
    """Close any windows showImage() opened."""
    if not _windows:
        return
    try:
        _cv().destroyAllWindows()
    except Exception:                       # noqa: BLE001 -- shutting down anyway
        pass
    _windows.clear()


def saveImage(picture, filename="photo.jpg"):
    """Save a picture to a file. Returns the filename.

        saveImage(picture)
        saveImage(picture, "faces.jpg")

    Useful when there's no window -- over plain ssh, or in a script you leave
    running.
    """
    _check_image(picture, "saveImage()")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename should be some text, like 'photo.jpg'")

    cv2 = _cv()
    if not cv2.imwrite(filename, picture):
        raise RuntimeError(
            f"couldn't write {filename}. Is the folder writable, and does the "
            "name end in .jpg or .png?")
    return filename


def wait(seconds):
    """Pause your script for a while.

    getFrame() already waits for the next frame, so you rarely need this in a
    camera loop -- it's here for pausing between pictures on purpose.
    """
    _check_number(seconds, "seconds", 0, 600)
    time.sleep(seconds)


# ---------------------------------------------------------------------------

def _cleanup():
    """Leave nothing running when the script ends, however it ends."""
    disconnect()
    closeWindows()


atexit.register(_cleanup)


def showHelp():
    """Print every command in this library."""
    print(f"""
robocam {__version__} -- see through your robot's camera, in your own scripts

Runs in the VM. The robot films; all the seeing happens here.
Start the camera on the robot first: cockpit, item 7.

  CONNECTING
    connect(3)                which robot to watch. 'A' and 'robot-3.local' work
    isConnected()             True once you have
    disconnect()              stop watching (happens by itself at the end)

  PICTURES
    getFrame()                the newest picture. Waits for a fresh one, so a
                              loop runs at the stream's own speed
    getFrameAge()             how old that picture already was, in seconds --
                              your honest lag
    showImage(picture)        show it in a window. False when q, Esc or the
                              window's X says stop:
                                while cam.showImage(cam.getFrame()):
                                    pass
    saveImage(picture, name)  write it to a file

  SEEING THINGS
    findFaces(picture)        -> picture with boxes, list of faces
        Each face: x, y, width, height, cx, cy, size. Biggest first, so
        faces[0] is the closest person.
          picture, faces = cam.findFaces(picture)
          if faces:
              print("nearest face at", faces[0]["cx"])

    getSkeleton(picture)      -> picture with a skeleton, dict of joints
        Joints by name, each with x, y and score. Missing ones are absent:
          picture, joints = cam.getSkeleton(picture)
          if "right_wrist" in joints:
              print("hand at", joints["right_wrist"]["x"])
        Names: {", ".join(JOINTS[:5])},
               {", ".join(JOINTS[5:9])},
               {", ".join(JOINTS[9:])}
        Currently using: {_pose.describe()}

  OTHER
    wait(seconds)             pause your script
    showHelp()                print this

A whole script looks like this:

  import robocam as cam

  cam.connect(3)                            # your robot's number

  while True:
      picture = cam.getFrame()              # newest frame from the robot
      picture, faces = cam.findFaces(picture)

      if faces:
          print("face at", faces[0]["cx"], "lag", cam.getFrameAge(), "s")

      if not cam.showImage(picture):        # q, Esc or closing the window
          break

Both findFaces() and getSkeleton() hand back a *copy* with the drawing on it, so
the original picture is still clean if you want to use it for something else.
""")
