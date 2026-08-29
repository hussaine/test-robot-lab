#!/usr/bin/env python3
"""A tiny, safe TCP command server for a PiCar-X.

Run this on the Pi:

    python3 robot_server.py

It accepts only newline-delimited PING, STOP, STEER <angle>, FORWARD <speed>,
and DISTANCE commands.
"""

import math
import socket

import roboshine as robot


HOST = "0.0.0.0"
PORT = 8765


def safe_stop():
    """Leave the robot stationary with its wheels pointing forward."""
    robot.stop()
    robot.steerStraight()


def command_reply(command):
    """Handle one allowed command. Nothing supplied by a client is executed."""
    words = command.split()

    if words == ["PING"]:
        return "PONG"
    if words == ["STOP"]:
        safe_stop()
        return "OK"
    if words == ["DISTANCE"]:
        try:
            distance = float(robot.get_distance_cm())
        except Exception as exc:
            print("distance error:", exc)
            return "ERROR distance is unavailable"
        #if not math.isfinite(distance) or distance < 0:
        #    return "ERROR distance is unavailable or invalid"
        return f"DISTANCE {distance:.1f}"
    if len(words) != 2:
        return "ERROR use PING, STOP, STEER <angle>, FORWARD <speed>, or DISTANCE"

    if words[0] == "STEER":
        try:
            angle = float(words[1])
        except ValueError:
            return "ERROR steering angle must be a number"
        if not math.isfinite(angle) or not -30 <= angle <= 30:
            return "ERROR steering angle must be from -30 through +30"

        robot.steer(angle)
        return "OK"

    if words[0] == "FORWARD":
        try:
            speed = float(words[1])
        except ValueError:
            return "ERROR forward speed must be a number"
        if not math.isfinite(speed) or not 0 <= speed <= 100:
            return "ERROR forward speed must be from 0 through 100"

        if speed == 0:
            safe_stop()
        else:
            robot.driveForward(speed)
        return "OK"

    return "ERROR use PING, STOP, STEER <angle>, FORWARD <speed>, or DISTANCE"


def serve_client(client, address):
    """Serve one client until it disconnects, then stop and straighten."""
    print("connected:", address[0])
    try:
        with client:
            with client.makefile("r", encoding="utf-8", newline="\n") as input_file:
                for line in input_file:
                    reply = command_reply(line.strip())
                    client.sendall((reply + "\n").encode("utf-8"))
    except OSError as exc:
        print("client connection error:", exc)
    finally:
        safe_stop()
        print("disconnected: motors stopped and wheels straightened")


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        print(f"robot server listening on {HOST}:{PORT}")

        while True:
            client, address = server.accept()
            serve_client(client, address)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        safe_stop()
