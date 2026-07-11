import curses
import threading
import time

import cv2
from flask import Flask, Response, jsonify, render_template_string
from gpiozero import Motor, PWMOutputDevice

# =========================
# PARTIE MOTEURS
# =========================

VALID_AXES = {"forward", "backward", "left", "right"}


class Vehicle:
    """Contrôle différentiel : combine avancer/reculer + gauche/droite."""

    def __init__(self):
        self._lock = threading.Lock()
        self._forward = False
        self._backward = False
        self._left = False
        self._right = False

        self.left_motor = Motor(forward=17, backward=22)
        self.left_pwm = PWMOutputDevice(18)
        self.right_motor = Motor(forward=23, backward=24)
        self.right_pwm = PWMOutputDevice(13)

    def set_axis(self, axis: str, active: bool) -> bool:
        if axis not in VALID_AXES:
            return False

        with self._lock:
            if axis == "forward":
                self._forward = active
                if active:
                    self._backward = False
            elif axis == "backward":
                self._backward = active
                if active:
                    self._forward = False
            elif axis == "left":
                self._left = active
                if active:
                    self._right = False
            elif axis == "right":
                self._right = active
                if active:
                    self._left = False

            self._apply_motors()
        return True

    def stop_all(self):
        with self._lock:
            self._forward = False
            self._backward = False
            self._left = False
            self._right = False
            self._apply_motors()

    def active_state(self) -> dict:
        with self._lock:
            return {
                "forward": self._forward,
                "backward": self._backward,
                "left": self._left,
                "right": self._right,
            }

    def _apply_motors(self):
        throttle = 0.0
        if self._forward:
            throttle = 1.0
        elif self._backward:
            throttle = -1.0

        steer = 0.0
        if self._left:
            steer = -1.0
        elif self._right:
            steer = 1.0

        left_speed = max(-1.0, min(1.0, throttle + steer))
        right_speed = max(-1.0, min(1.0, throttle - steer))

        self._drive_side(self.left_motor, self.left_pwm, left_speed)
        self._drive_side(self.right_motor, self.right_pwm, right_speed)

    @staticmethod
    def _drive_side(motor, pwm, speed: float):
        if speed > 0:
            pwm.value = 1
            motor.forward()
        elif speed < 0:
            pwm.value = 1
            motor.backward()
        else:
            motor.stop()
            pwm.value = 0

    def map_key_to_axis(self, key):
        return {
            curses.KEY_UP: "forward",
            curses.KEY_DOWN: "backward",
            curses.KEY_LEFT: "left",
            curses.KEY_RIGHT: "right",
        }.get(key)


rpi_vehicle = Vehicle()


# =========================
# PARTIE CAMERA FLASK
# =========================

app = Flask(__name__)

CAMERA_INDEX = 0
WIDTH = 640
HEIGHT = 360
FPS = 20
JPEG_QUALITY = 60

camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
camera.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
camera.set(cv2.CAP_PROP_FPS, FPS)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not camera.isOpened():
    print("Erreur : impossible d'ouvrir la caméra /dev/video0")
    exit(1)

html_page = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Caméra Raspberry Pi</title>
    <style>
        body {
            background: #111;
            color: white;
            font-family: Arial, sans-serif;
            text-align: center;
        }
        h1 { margin-top: 20px; }
        img {
            width: 90%;
            max-width: 900px;
            border: 3px solid white;
            border-radius: 10px;
        }
        .info { margin-top: 15px; color: #ccc; }
    </style>
</head>
<body>
    <h1>Flux caméra Raspberry Pi</h1>
    <img src="/video">
    <div class="info">
        Caméra USB → Raspberry Pi → App mobile
    </div>
</body>
</html>
"""


def generate_frames():
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

    while True:
        success, frame = camera.read()
        if not success:
            print("Erreur : image non lue depuis la caméra")
            time.sleep(0.05)
            continue

        ret, buffer = cv2.imencode(".jpg", frame, encode_param)
        if not ret:
            print("Erreur : encodage JPEG impossible")
            continue

        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


@app.route("/")
def index():
    return render_template_string(html_page)


@app.route("/video")
def video():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/status")
def status():
    return jsonify({
        "camera": "connected",
        "device": "/dev/video0",
        "resolution": f"{WIDTH}x{HEIGHT}",
        "fps": FPS,
        "jpeg_quality": JPEG_QUALITY,
        "motors": rpi_vehicle.active_state(),
    })


@app.route("/control/press/<command>")
def control_press(command: str):
    if not rpi_vehicle.set_axis(command, True):
        return jsonify({"ok": False, "error": f"Commande inconnue : {command}"}), 404
    return jsonify({"ok": True, "action": "press", "command": command, "active": rpi_vehicle.active_state()})


@app.route("/control/release/<command>")
def control_release(command: str):
    if not rpi_vehicle.set_axis(command, False):
        return jsonify({"ok": False, "error": f"Commande inconnue : {command}"}), 404
    return jsonify({"ok": True, "action": "release", "command": command, "active": rpi_vehicle.active_state()})


@app.route("/control/stop")
def control_stop():
    rpi_vehicle.stop_all()
    return jsonify({"ok": True, "action": "stop", "active": rpi_vehicle.active_state()})


def start_camera_server():
    print("Serveur RC Camera démarré")
    print("Page web   : http://IP_DU_RASPBERRY:5000")
    print("Flux vidéo : http://IP_DU_RASPBERRY:5000/video")
    print("Contrôle   : GET /control/press/<forward|backward|left|right>")
    print("             GET /control/release/<forward|backward|left|right>")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


# =========================
# PARTIE CONTROLE CLAVIER
# =========================

def main(window):
    window.clear()
    window.addstr("Contrôle voiture RC\n")
    window.addstr("Flèches : avancer / reculer / gauche / droite (combinables)\n")
    window.addstr("Q : quitter\n")
    window.refresh()

    next_key = None

    while True:
        curses.halfdelay(1)

        if next_key is None:
            key = window.getch()
        else:
            key = next_key
            next_key = None

        if key == ord("q") or key == ord("Q"):
            rpi_vehicle.stop_all()
            break

        if key != -1:
            axis = rpi_vehicle.map_key_to_axis(key)
            if axis:
                rpi_vehicle.set_axis(axis, True)
                next_key = key

                while next_key == key:
                    next_key = window.getch()

                rpi_vehicle.set_axis(axis, False)


# =========================
# LANCEMENT DU PROGRAMME
# =========================

if __name__ == "__main__":
    try:
        camera_thread = threading.Thread(target=start_camera_server, daemon=True)
        camera_thread.start()
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("Arrêt du programme")
    finally:
        rpi_vehicle.stop_all()
        camera.release()
        print("Moteurs arrêtés et caméra libérée")
