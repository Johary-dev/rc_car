"""
Pilotage MANUEL de la voiture RC.

Logique identique à main.py avec deux améliorations :
  - La caméra n'est plus bloquante : si elle est absente au démarrage,
    le script continue et le pilotage reste disponible.
  - Le contrôle HTTP utilise le modèle proportionnel (accélérateur + virage)
    issu de follow_line.py pour une meilleure maniabilité.

Routes Flask disponibles :
  /status               → état complet
  /switch/auto          → bascule vers auto_drive.py (pilotage automatique)
  /control/press/<cmd>  → commande directionnelle
  /control/release/<cmd>
  /control/throttle/<-100..100>
  /control/stop

Lancement : python manual_drive.py
"""

import curses
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
from flask import Flask, Response, jsonify, render_template_string
from gpiozero import Motor, PWMOutputDevice

SCRIPTS_DIR = Path(__file__).parent

# ==========================================================
# MOTEURS
# ==========================================================

VALID_AXES = {"forward", "backward", "left", "right"}

left_motor  = Motor(forward=17, backward=22)
left_pwm    = PWMOutputDevice(18)
right_motor = Motor(forward=23, backward=24)
right_pwm   = PWMOutputDevice(13)

motor_lock       = threading.Lock()
manual_state_lock = threading.Lock()

throttle         = 0.0
is_left          = False
is_right         = False
current_left_speed  = 0.0
current_right_speed = 0.0


def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def drive_side(motor, pwm, speed: float):
    speed     = clamp(speed)
    magnitude = abs(speed)
    if magnitude == 0:
        motor.stop()
        pwm.value = 0
        return
    pwm.value = magnitude
    if speed > 0:
        motor.forward()
    else:
        motor.backward()


def set_motor_speeds(left_speed: float, right_speed: float):
    global current_left_speed, current_right_speed
    left_speed  = clamp(left_speed)
    right_speed = clamp(right_speed)
    with motor_lock:
        drive_side(left_motor,  left_pwm,  left_speed)
        drive_side(right_motor, right_pwm, right_speed)
        current_left_speed  = left_speed
        current_right_speed = right_speed


def stop_motors():
    set_motor_speeds(0.0, 0.0)


def motor_state() -> dict:
    with motor_lock:
        return {
            "left_speed":  current_left_speed,
            "right_speed": current_right_speed,
        }


# ==========================================================
# CONTRÔLE MANUEL
# ==========================================================


def apply_manual_motors():
    steer = -1.0 if is_left else (1.0 if is_right else 0.0)
    speed_limit     = abs(throttle)
    effective_steer = steer * speed_limit
    left_speed  = clamp(throttle + effective_steer, -speed_limit, speed_limit)
    right_speed = clamp(throttle - effective_steer, -speed_limit, speed_limit)
    set_motor_speeds(left_speed, right_speed)


def set_axis(axis: str, active: bool) -> bool:
    global throttle, is_left, is_right
    if axis not in VALID_AXES:
        return False
    with manual_state_lock:
        if axis == "forward":
            throttle = 1.0 if active else 0.0
        elif axis == "backward":
            throttle = -1.0 if active else 0.0
        elif axis == "left":
            is_left = active
            if active:
                is_right = False
        elif axis == "right":
            is_right = active
            if active:
                is_left = False
        apply_manual_motors()
    return True


def set_throttle(value: float) -> bool:
    global throttle
    with manual_state_lock:
        throttle = clamp(value)
        apply_manual_motors()
    return True


def stop_all():
    global throttle, is_left, is_right
    with manual_state_lock:
        throttle = 0.0
        is_left  = False
        is_right = False
    stop_motors()


def manual_state() -> dict:
    with manual_state_lock:
        return {"throttle": throttle, "left": is_left, "right": is_right}


def map_key_to_axis(key):
    return {
        curses.KEY_UP:    "forward",
        curses.KEY_DOWN:  "backward",
        curses.KEY_LEFT:  "left",
        curses.KEY_RIGHT: "right",
    }.get(key)


# ==========================================================
# CAMÉRA ET SERVEUR FLASK
# ==========================================================

app = Flask(__name__)

CAMERA_INDEX  = 0
WIDTH         = 640
HEIGHT        = 360
FPS           = 20
JPEG_QUALITY  = 60

camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FOURCC,    cv2.VideoWriter_fourcc(*"MJPG"))
camera.set(cv2.CAP_PROP_FRAME_WIDTH,  WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
camera.set(cv2.CAP_PROP_FPS,          FPS)
camera.set(cv2.CAP_PROP_BUFFERSIZE,   1)

# La caméra n'est plus bloquante : le pilotage manuel fonctionne même
# si aucune caméra n'est branchée.
camera_available = camera.isOpened()
if not camera_available:
    print("Attention : impossible d'ouvrir la caméra /dev/video0")
    print("Le pilotage manuel reste disponible sans flux vidéo.")

shutdown_event = threading.Event()

html_page = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Voiture RC — Manuel</title>
    <style>
        body { background:#111; color:white; font-family:Arial,sans-serif; text-align:center; }
        img  { width:90%; max-width:900px; border:3px solid white; border-radius:10px; }
        .info { margin:15px; color:#ccc; }
    </style>
</head>
<body>
    <h1>Voiture RC — pilotage manuel</h1>
    <img src="/video" alt="Flux caméra">
    <div class="info">État complet : <code>/status</code></div>
</body>
</html>
"""


def generate_frames():
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    while not shutdown_event.is_set():
        if not camera_available:
            time.sleep(0.5)
            continue
        success, frame = camera.read()
        if not success:
            time.sleep(0.05)
            continue
        ret, buffer = cv2.imencode(".jpg", frame, encode_param)
        if not ret:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )


@app.route("/")
def index():
    return render_template_string(html_page)


@app.route("/video")
def video():
    if not camera_available:
        return jsonify({"ok": False, "error": "Caméra indisponible"}), 503
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/status")
def status():
    return jsonify({
        "mode":         "manual",
        "camera":       "connected" if camera_available else "disconnected",
        "device":       "/dev/video0",
        "resolution":   f"{WIDTH}x{HEIGHT}",
        "fps":          FPS,
        "jpeg_quality": JPEG_QUALITY,
        "motors":       motor_state(),
        "manual":       manual_state(),
    })


@app.route("/control/press/<command>")
def control_press(command: str):
    if not set_axis(command, True):
        return jsonify({"ok": False, "error": f"Commande inconnue : {command}"}), 404
    return jsonify({"ok": True, "action": "press", "command": command, "manual": manual_state(), "motors": motor_state()})


@app.route("/control/release/<command>")
def control_release(command: str):
    if not set_axis(command, False):
        return jsonify({"ok": False, "error": f"Commande inconnue : {command}"}), 404
    return jsonify({"ok": True, "action": "release", "command": command, "manual": manual_state(), "motors": motor_state()})


@app.route("/control/throttle/<raw_value>")
def control_throttle(raw_value: str):
    try:
        percent = int(raw_value)
    except ValueError:
        return jsonify({"ok": False, "error": "Valeur invalide, doit être un entier"}), 400
    if not -100 <= percent <= 100:
        return jsonify({"ok": False, "error": "La valeur doit être entre -100 et 100"}), 400
    set_throttle(percent / 100.0)
    return jsonify({"ok": True, "action": "throttle", "throttle": percent, "motors": motor_state()})


@app.route("/control/stop")
def control_stop():
    stop_all()
    return jsonify({"ok": True, "action": "stop", "motors": motor_state()})


# ==========================================================
# BASCULEMENT VERS LE PILOTAGE AUTOMATIQUE
# ==========================================================

def _do_switch_auto():
    """Exécuté dans un thread séparé pour laisser Flask envoyer la réponse."""
    time.sleep(0.4)          # Attendre que la réponse HTTP soit envoyée
    stop_all()
    # Libération explicite des GPIO avant de quitter
    try:
        left_pwm.close()
        right_pwm.close()
        left_motor.close()
        right_motor.close()
        if camera_available:
            camera.release()
    except Exception:
        pass
    # Démarrer auto_drive.py comme processus indépendant
    subprocess.Popen(
        [sys.executable, str(SCRIPTS_DIR / "auto_drive.py")],
        start_new_session=True,
    )
    time.sleep(0.2)
    os._exit(0)   # Quitter immédiatement (libère le port 5000)


@app.route("/switch/auto")
def switch_to_auto():
    """Bascule vers le pilotage automatique (suivi de ligne)."""
    threading.Thread(target=_do_switch_auto, daemon=True).start()
    return jsonify({"ok": True, "switching_to": "auto"})


def start_camera_server():
    print("Serveur RC Camera démarré (mode MANUEL)")
    print("Page web  : http://IP_DU_RASPBERRY:5000")
    print("État      : http://IP_DU_RASPBERRY:5000/status")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True, use_reloader=False)


# ==========================================================
# CONTRÔLE CLAVIER (curses)
# ==========================================================


def main(window):
    window.clear()
    window.addstr("Contrôle voiture RC — pilotage manuel\n")
    window.addstr("Flèches : avancer / reculer / gauche / droite\n")
    window.addstr("Q : quitter\n")
    window.refresh()

    next_key = None
    while True:
        curses.halfdelay(1)
        key      = window.getch() if next_key is None else next_key
        next_key = None

        if key in (ord("q"), ord("Q")):
            stop_all()
            break

        if key != -1:
            axis = map_key_to_axis(key)
            if axis:
                set_axis(axis, True)
                next_key = key
                while next_key == key:
                    next_key = window.getch()
                set_axis(axis, False)


# ==========================================================
# LANCEMENT
# ==========================================================

if __name__ == "__main__":
    try:
        threading.Thread(target=start_camera_server, daemon=True).start()

        if sys.stdin.isatty():
            # Terminal disponible → contrôle clavier + serveur Flask
            curses.wrapper(main)
        else:
            # Lancé en arrière-plan (via subprocess depuis auto_drive.py)
            # → serveur Flask uniquement, pas de curses
            print("Mode arrière-plan : contrôle via l'app mobile uniquement.")
            shutdown_event.wait()

    except KeyboardInterrupt:
        print("Arrêt du programme")
    finally:
        shutdown_event.set()
        stop_all()
        if camera_available:
            camera.release()
        left_pwm.close()
        right_pwm.close()
        left_motor.close()
        right_motor.close()
        print("Moteurs arrêtés et caméra libérée")
