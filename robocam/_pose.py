"""Finding body joints in an image. Plumbing -- students use robocam.getSkeleton().

Two backends, tried in this order:

1. **MediaPipe** (`import mediapipe`) -- best quality, no model file to manage,
   33 landmarks of which we keep the 13 that matter for a body skeleton.
2. **OpenCV's DNN module** with an OpenPose-style Caffe model in
   ~/.robocam/models -- works with nothing but apt's OpenCV, at the cost of a
   model download and a slower frame rate.

Both are reduced to the same 13 named joints, so a student's script doesn't
change if the backend does. Whichever loads first is used for the rest of the
session; if neither is available, getSkeleton() raises with the command to run.

Both paths are single-person on purpose. Two-person pose needs part-affinity
grouping, which is a lot of complexity for a camp -- and MediaPipe is
single-person by design anyway, so supporting crowds on one backend only would
be a difference students would trip over.
"""

import os

# The joints we promise, whatever the backend. Ordered head-down so printing a
# skeleton reads naturally.
JOINTS = (
    "nose",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
)

# Which joints to join up when drawing. Not a full body graph -- just the lines
# that make a person recognisable.
BONES = (
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
)

MODEL_DIR = os.path.expanduser("~/.robocam/models")

# MediaPipe's landmark numbers for the joints we keep. These indices are part of
# its published landmark order, not something we can look up by name at runtime.
_MEDIAPIPE_INDEX = {
    "nose": 0,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}

# OpenPose channel order. The MPI model publishes 15 joints plus a background
# channel; COCO publishes 18 plus background -- so the channel count tells us
# which one has been downloaded.
_OPENPOSE_MPI = {
    "nose": 0,                              # MPI calls it "head"
    "right_shoulder": 2, "right_elbow": 3, "right_wrist": 4,
    "left_shoulder": 5, "left_elbow": 6, "left_wrist": 7,
    "right_hip": 8, "right_knee": 9, "right_ankle": 10,
    "left_hip": 11, "left_knee": 12, "left_ankle": 13,
}
_OPENPOSE_COCO = {
    "nose": 0,
    "right_shoulder": 2, "right_elbow": 3, "right_wrist": 4,
    "left_shoulder": 5, "left_elbow": 6, "left_wrist": 7,
    "right_hip": 8, "right_knee": 9, "right_ankle": 10,
    "left_hip": 11, "left_knee": 12, "left_ankle": 13,
}

MIN_SCORE = 0.1         # below this a joint is treated as not found at all


class PoseUnavailable(RuntimeError):
    """Neither backend could be loaded."""


class _MediaPipeBackend:
    name = "mediapipe"

    def __init__(self):
        import mediapipe                                    # noqa: PLC0415
        self._mp = mediapipe
        # static_image_mode=False lets it track between frames, which is both
        # faster and steadier on a video stream than detecting from scratch.
        self._pose = mediapipe.solutions.pose.Pose(
            static_image_mode=False, model_complexity=1,
            min_detection_confidence=0.5, min_tracking_confidence=0.5)

    def find_points(self, image, cv2):
        height, width = image.shape[:2]
        # MediaPipe wants RGB; OpenCV gives us BGR.
        result = self._pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        landmarks = getattr(result, "pose_landmarks", None)
        if landmarks is None:
            return {}

        points = {}
        for joint, index in _MEDIAPIPE_INDEX.items():
            mark = landmarks.landmark[index]
            score = float(getattr(mark, "visibility", 1.0))
            if score < MIN_SCORE:
                continue
            # Landmarks are fractions of the image, and can sit slightly outside
            # it when a limb is cut off by the edge of frame.
            points[joint] = {
                "x": int(round(mark.x * width)),
                "y": int(round(mark.y * height)),
                "score": round(score, 3),
            }
        return points


class _DnnBackend:
    """OpenPose-style heatmaps through cv2.dnn.

    Single person, so the maths is just "brightest pixel in each joint's
    heatmap" -- no part-affinity fields, no grouping.
    """

    name = "opencv-dnn"
    INPUT = 368         # what these models were trained at

    def __init__(self, cv2):
        prototxt, weights = self._find_model()
        self._net = cv2.dnn.readNetFromCaffe(prototxt, weights)
        self._cv2 = cv2
        self._layout = None         # decided from the first frame's output
        self.model = os.path.basename(weights)

    @staticmethod
    def _find_model():
        if not os.path.isdir(MODEL_DIR):
            raise FileNotFoundError(MODEL_DIR)
        prototxt = weights = None
        for entry in sorted(os.listdir(MODEL_DIR)):
            path = os.path.join(MODEL_DIR, entry)
            if entry.endswith(".prototxt"):
                prototxt = prototxt or path
            elif entry.endswith(".caffemodel"):
                weights = weights or path
        if not (prototxt and weights):
            raise FileNotFoundError(
                f"need a .prototxt and a .caffemodel in {MODEL_DIR}")
        return prototxt, weights

    def find_points(self, image, cv2):
        height, width = image.shape[:2]
        blob = cv2.dnn.blobFromImage(
            image, 1.0 / 255, (self.INPUT, self.INPUT), (0, 0, 0),
            swapRB=False, crop=False)
        self._net.setInput(blob)
        out = self._net.forward()

        channels = out.shape[1]
        if self._layout is None:
            # 15 joints + background, or 18 + background.
            self._layout = _OPENPOSE_COCO if channels >= 19 else _OPENPOSE_MPI

        map_height, map_width = out.shape[2], out.shape[3]
        points = {}
        for joint, index in self._layout.items():
            if index >= channels:
                continue
            heat = out[0, index, :, :]
            _, score, _, location = cv2.minMaxLoc(heat)
            if score < MIN_SCORE:
                continue
            points[joint] = {
                "x": int(round(location[0] * width / map_width)),
                "y": int(round(location[1] * height / map_height)),
                "score": round(float(score), 3),
            }
        return points


_backend = None
_failure = None


def backend(cv2):
    """The pose backend, loaded once on first use.

    Raises PoseUnavailable with instructions if neither backend is installed.
    """
    global _backend, _failure
    if _backend is not None:
        return _backend
    if _failure is not None:
        raise _failure

    problems = []
    try:
        _backend = _MediaPipeBackend()
        return _backend
    except Exception as exc:                # noqa: BLE001 -- try the next one
        problems.append(f"mediapipe: {type(exc).__name__}: {exc}")

    try:
        _backend = _DnnBackend(cv2)
        return _backend
    except Exception as exc:                # noqa: BLE001
        problems.append(f"opencv-dnn: {type(exc).__name__}: {exc}")

    detail = "\n    ".join(problems)
    _failure = PoseUnavailable(
        "getSkeleton() needs a pose model, and neither option is ready:\n"
        f"    {detail}\n\n"
        "Install one, once, with:\n"
        "    bash ~/test-robot-lab/setup-pose.sh\n\n"
        "findFaces() does not need any of this and works already.")
    raise _failure


def describe():
    """Which backend is in use, for showHelp() and error messages."""
    if _backend is None:
        return "not loaded yet"
    extra = getattr(_backend, "model", None)
    return f"{_backend.name} ({extra})" if extra else _backend.name
