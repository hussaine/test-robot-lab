## steering test

python3 - <<'PY'
import time
import roboshine as robot

def test(name, angle):
    print(name, angle)
    robot.stop()
    robot.steer(angle)
    time.sleep(1)
    robot.driveForward(15)
    time.sleep(1.0)
    robot.stop()
    time.sleep(2)

test("LEFT", -20)
test("STRAIGHT", 0)
test("RIGHT", 20)

robot.steer(0)
print("done")
PY


