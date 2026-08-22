"""Reading the robot's MJPEG stream. Plumbing -- students use robocam instead.

The one design decision worth knowing about: this keeps only the newest frame and
throws the rest away. cv2.VideoCapture buffers internally, so computer vision
slower than the stream falls further and further behind until the picture is
seconds stale -- fine for recording, useless for anything that steers. A reader
thread here fills a one-frame slot and older frames are dropped on the floor.

cvclient.py has its own copy of this logic, from before robocam existed. If you
are changing something here, check whether it needs changing there too.
"""

import threading
import time
import urllib.request

DEFAULT_PORT = 8080


def resolve_host(label):
    """Work out the robot's hostname from whatever the student typed.

    Robots are named robot-1, robot-A and so on, so a bare number *or* letter is
    a suffix, not a hostname. Anything containing a dot is taken as given.

        3              -> robot-3.local
        A              -> robot-A.local
        robot-a        -> robot-a.local
        robot-a.local  -> robot-a.local
        10.0.0.7       -> 10.0.0.7
    """
    label = str(label).strip()
    if not label:
        raise ValueError("which robot? Try connect(3), or connect('A')")
    if "." in label:
        return label                        # a hostname or an IP; use it as-is
    if not label.lower().startswith("robot-"):
        label = f"robot-{label}"
    return f"{label}.local"


class NewestFrame:
    """Holds the most recent JPEG. Older frames are dropped, on purpose."""

    def __init__(self):
        self.jpeg = None
        self.stamp = 0.0
        self.count = 0
        self.error = None
        self.lock = threading.Lock()
        self.arrived = threading.Event()

    def put(self, jpeg):
        with self.lock:
            self.jpeg = jpeg
            self.stamp = time.monotonic()
            self.count += 1
        self.arrived.set()

    def take(self):
        """Return (jpeg, age_seconds), or (None, 0.0) if nothing is waiting."""
        with self.lock:
            if self.jpeg is None:
                self.arrived.clear()
                return None, 0.0
            jpeg, stamp = self.jpeg, self.stamp
            self.jpeg = None            # never hand the same frame out twice
            self.arrived.clear()
        return jpeg, time.monotonic() - stamp


def reader(url, newest, stop):
    """Pull the multipart MJPEG stream, splitting it into whole JPEGs.

    Scanning for the JPEG markers is safe: 0xFF bytes inside compressed data are
    byte-stuffed as 0xFF00, so a bare 0xFFD9 only ever means end-of-image.

    Any failure is recorded on `newest.error` rather than raised, because this
    runs on a background thread where an exception would vanish silently.
    """
    SOI, EOI = b"\xff\xd8", b"\xff\xd9"
    try:
        with urllib.request.urlopen(url, timeout=10) as stream:
            buffer = bytearray()
            while not stop.is_set():
                chunk = stream.read(8192)
                if not chunk:
                    break
                buffer += chunk
                while True:
                    start = buffer.find(SOI)
                    if start < 0:
                        del buffer[:-1]
                        break
                    end = buffer.find(EOI, start + 2)
                    if end < 0:
                        del buffer[:start]
                        break
                    newest.put(bytes(buffer[start:end + 2]))
                    del buffer[:end + 2]
    except Exception as exc:                # noqa: BLE001 -- reported, not raised
        newest.error = exc
    finally:
        # Wake anyone waiting, so a dead stream surfaces as an error instead of
        # hanging until their timeout expires.
        newest.arrived.set()


class Stream:
    """A running connection to one robot's camera."""

    def __init__(self, host, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}/stream.mjpg"
        self.newest = NewestFrame()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=reader, args=(self.url, self.newest, self._stop), daemon=True)
        self._thread.start()

    @property
    def error(self):
        return self.newest.error

    @property
    def frames_seen(self):
        return self.newest.count

    def next_jpeg(self, timeout):
        """Wait up to `timeout` seconds for a frame that hasn't been seen yet.

        Returns (jpeg, age) or (None, 0.0) on timeout.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            jpeg, age = self.newest.take()
            if jpeg is not None:
                return jpeg, age
            if self.newest.error is not None:
                return None, 0.0
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, 0.0
            self.newest.arrived.wait(min(remaining, 0.25))

    def close(self):
        self._stop.set()
