"""
Serveur RC unifié — pilotage manuel + automatique dans UN seul processus.

Architecture :
  drive_control.py  → GPIO moteurs + set_axis / set_throttle (API commune)
  line_auto.py      → capteurs FC-51 ; envoie les directions via set_axis
  rc_unified.py     → Flask, caméra, batterie, bascule de mode in-process

Le switch manuel ↔ auto ne redémarre plus de programme :
  /switch/auto   → active la boucle de suivi de ligne
  /switch/manual → désactive l'autopilote, contrôle API uniquement

Lancement : python rc_unified.py
"""

from __future__ import annotations

import threading
import time

import cv2
from flask import Flask, Response, jsonify, render_template_string

import drive_control
import line_auto
from batterie_ina219 import CapteurBatterie

battery_sensor = CapteurBatterie()
shutdown_event = threading.Event()

# ==========================================================
# CAMÉRA (non bloquante)
# ==========================================================

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

camera_available = camera.isOpened()
if not camera_available:
    print("Attention : caméra /dev/video0 indisponible — pilotage toujours possible.")

# ==========================================================
# FLASK
# ==========================================================

app = Flask(__name__)

html_page = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Voiture RC — Unifié</title>
    <style>
        body { background:#111; color:white; font-family:Arial,sans-serif; text-align:center; }
        img  { width:90%; max-width:900px; border:3px solid white; border-radius:10px; }
        .info { margin:15px; color:#ccc; }
    </style>
</head>
<body>
    <h1>Voiture RC — manuel + automatique</h1>
    <img src="/video" alt="Flux caméra">
    <div class="info">État : <code>/status</code> — switch : <code>/switch/auto</code> | <code>/switch/manual</code></div>
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
    mode = "auto" if drive_control.is_autopilot_enabled() else "manual"
    return jsonify({
        "mode": mode,
        "camera": "connected" if camera_available else "disconnected",
        "device": "/dev/video0",
        "resolution": f"{WIDTH}x{HEIGHT}",
        "fps": FPS,
        "jpeg_quality": JPEG_QUALITY,
        "battery": battery_sensor.lire_pourcentage(),
        "motors": drive_control.motor_state(),
        "manual": drive_control.manual_state(),
        "line_follower": line_auto.line_follower_state(),
    })


# ---------- Contrôle manuel (API) ----------

@app.route("/control/press/<command>")
def control_press(command: str):
    if not drive_control.set_axis(command, True, source="manual"):
        return jsonify({"ok": False, "error": f"Commande inconnue : {command}"}), 404
    return jsonify({
        "ok": True,
        "action": "press",
        "command": command,
        "manual": drive_control.manual_state(),
        "motors": drive_control.motor_state(),
    })


@app.route("/control/release/<command>")
def control_release(command: str):
    if not drive_control.set_axis(command, False, source="manual"):
        return jsonify({"ok": False, "error": f"Commande inconnue : {command}"}), 404
    return jsonify({
        "ok": True,
        "action": "release",
        "command": command,
        "manual": drive_control.manual_state(),
        "motors": drive_control.motor_state(),
    })


@app.route("/control/throttle/<raw_value>")
def control_throttle(raw_value: str):
    try:
        percent = int(raw_value)
    except ValueError:
        return jsonify({"ok": False, "error": "Valeur invalide, doit être un entier"}), 400
    if not -100 <= percent <= 100:
        return jsonify({"ok": False, "error": "La valeur doit être entre -100 et 100"}), 400
    drive_control.set_throttle(percent / 100.0, source="manual")
    return jsonify({
        "ok": True,
        "action": "throttle",
        "throttle": percent,
        "motors": drive_control.motor_state(),
    })


@app.route("/control/stop")
def control_stop():
    drive_control.stop_all(disable_autopilot=True)
    return jsonify({
        "ok": True,
        "action": "stop",
        "motors": drive_control.motor_state(),
        "line_follower": line_auto.line_follower_state(),
    })


@app.route("/control/autopilot/on")
def control_autopilot_on():
    drive_control.enable_auto_mode()
    return jsonify({
        "ok": True,
        "action": "autopilot_on",
        "line_follower": line_auto.line_follower_state(),
    })


@app.route("/control/autopilot/off")
def control_autopilot_off():
    drive_control.enable_manual_mode()
    return jsonify({
        "ok": True,
        "action": "autopilot_off",
        "line_follower": line_auto.line_follower_state(),
    })


# ---------- Bascule de mode (même processus, pas de redémarrage) ----------

@app.route("/switch/auto")
def switch_to_auto():
    drive_control.enable_auto_mode()
    return jsonify({
        "ok": True,
        "switching_to": "auto",
        "restart": False,
        "mode": "auto",
        "line_follower": line_auto.line_follower_state(),
    })


@app.route("/switch/manual")
def switch_to_manual():
    drive_control.enable_manual_mode()
    return jsonify({
        "ok": True,
        "switching_to": "manual",
        "restart": False,
        "mode": "manual",
        "line_follower": line_auto.line_follower_state(),
    })


def start_camera_server():
    print("Serveur RC unifié démarré")
    print("Page web     : http://IP_DU_RASPBERRY:5000")
    print("État         : http://IP_DU_RASPBERRY:5000/status")
    print("Switch auto  : /switch/auto   (in-process)")
    print("Switch manuel: /switch/manual (in-process)")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True, use_reloader=False)


# ==========================================================
# LANCEMENT
# ==========================================================

if __name__ == "__main__":
    try:
        # Démarre en mode manuel ; l'app active l'auto via /switch/auto
        drive_control.enable_manual_mode()

        line_thread = threading.Thread(
            target=line_auto.line_follower_loop,
            args=(shutdown_event,),
            daemon=True,
        )
        line_thread.start()

        print("Programme unifié lancé (manuel par défaut).")
        print("Ctrl+C pour arrêter.")
        start_camera_server()

    except KeyboardInterrupt:
        print("\nArrêt demandé")

    finally:
        shutdown_event.set()
        drive_control.cleanup()
        line_auto.cleanup()
        if camera_available:
            camera.release()
        print("Moteurs, capteurs et caméra libérés")
