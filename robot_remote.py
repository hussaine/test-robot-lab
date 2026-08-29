"""Send safe classroom-demo commands to robot_server.py on a Pi.

    import robot_remote as robot

    robot.connect("robot-3.local")
    robot.steer(-20)
    robot.stop()
    robot.close()
"""

import socket


_socket = None
_reader = None


def connect(host, port=8765):
    """Connect to a Pi running pi/robot_server.py."""
    global _socket, _reader

    close()
    try:
        _socket = socket.create_connection((host, port), timeout=5)
        _reader = _socket.makefile("r", encoding="utf-8", newline="\n")
    except OSError as exc:
        close()
        raise RuntimeError(f"can't connect to {host}:{port} ({exc})") from exc


def _send(command):
    """Send one command and return the server's one-line reply."""
    if _socket is None:
        raise RuntimeError("not connected yet. Call connect(host) first.")

    try:
        _socket.sendall((command + "\n").encode("utf-8"))
        reply = _reader.readline().strip()
    except OSError as exc:
        close()
        raise RuntimeError(f"connection to robot was lost ({exc})") from exc

    if not reply:
        close()
        raise RuntimeError("robot server closed the connection")
    if reply.startswith("ERROR"):
        raise RuntimeError(f"robot server says: {reply}")
    return reply


def _angle(angle):
    """Check an angle before sending it to the robot."""
    if isinstance(angle, bool) or not isinstance(angle, (int, float)):
        raise TypeError("angle should be a number from -30 through +30")
    if not -30 <= angle <= 30:
        raise ValueError(f"angle should be from -30 through +30, not {angle}")
    return angle


def _speed(speed):
    """Check a forward speed before sending it to the robot."""
    if isinstance(speed, bool) or not isinstance(speed, (int, float)):
        raise TypeError("speed should be a number from 0 through 300")
    if not 0 <= speed <= 300:
        raise ValueError(f"speed should be from 0 through 300, not {speed}")
    return speed


def steer(angle):
    """Set the front-wheel angle. Negative is left; positive is right."""
    _send(f"STEER {_angle(angle):g}")


def stop():
    """Stop the drive motors and straighten the front wheels."""
    _send("STOP")


def forward(speed):
    """Drive forward at a speed from 0 through 300; 0 stops safely."""
    _send(f"FORWARD {_speed(speed):g}")


def distance():
    """Return the ultrasonic distance reading in centimetres as a float."""
    reply = _send("DISTANCE")
    words = reply.split()
    if len(words) != 2 or words[0] != "DISTANCE":
        raise RuntimeError(f"unexpected reply from robot server: {reply}")
    try:
        value = float(words[1])
    except ValueError as exc:
        raise RuntimeError(f"invalid distance from robot server: {reply}") from exc
    return value


def ping():
    """Check that the server is responding. Returns 'PONG'."""
    reply = _send("PING")
    if reply != "PONG":
        raise RuntimeError(f"unexpected reply from robot server: {reply}")
    return reply


def close():
    """Close the connection. The server stops and straightens on disconnect."""
    global _socket, _reader

    if _reader is not None:
        _reader.close()
        _reader = None
    if _socket is not None:
        _socket.close()
        _socket = None
