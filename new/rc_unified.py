#!/usr/bin/env python3
"""
Serveur RC unifié — pilotage manuel + automatique dans UN seul processus.

Architecture :
    drive_control.py  -> GPIO moteurs + commandes partagées
    line_auto.py      -> lecture des FC-51 + suivi de ligne
    rc_unified.py     -> Flask, caméra, batterie et bascule de mode

Le changement manuel <-> automatique ne redémarre aucun programme.

Routes principales :
    /status
    /video

    /switch/auto
    /switch/manual

    /control/press/<command>
    /control/release/<command>
    /control/throttle/<-100..100>
    /control/stop

    /control/autopilot/on
    /control/autopilot/off

Lancement :
    python3 rc_unified.py
"""

from __future__ import annotations

import threading
import time

import cv2
from flask import Flask, Response, jsonify, render_template_string

import drive_control
import line_auto
from batterie_ina219 import CapteurBatterie


# ==========================================================
# ÉTAT GLOBAL
# ==========================================================

battery_sensor = CapteurBatterie()
shutdown_event = threading.Event()


# ==========================================================
# CAMÉRA NON BLOQUANTE
# ==========================================================

CAMERA_INDEX = 0

WIDTH = 640
HEIGHT = 360
FPS = 20
JPEG_QUALITY = 60

camera = cv2.VideoCapture(
    CAMERA_INDEX,
    cv2.CAP_V4L2,
)

camera.set(
    cv2.CAP_PROP_FOURCC,
    cv2.VideoWriter_fourcc(*"MJPG"),
)

camera.set(
    cv2.CAP_PROP_FRAME_WIDTH,
    WIDTH,
)

camera.set(
    cv2.CAP_PROP_FRAME_HEIGHT,
    HEIGHT,
)

camera.set(
    cv2.CAP_PROP_FPS,
    FPS,
)

camera.set(
    cv2.CAP_PROP_BUFFERSIZE,
    1,
)

camera_available = camera.isOpened()

if not camera_available:
    print(
        "Attention : caméra /dev/video0 indisponible "
        "— pilotage toujours possible."
    )


# ==========================================================
# FLASK
# ==========================================================

app = Flask(__name__)


html_page = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Smart RC Car</title>

    <style>
        body {
            margin: 0;
            padding: 20px;
            background: #111;
            color: white;
            font-family: Arial, sans-serif;
            text-align: center;
        }

        h1 {
            margin-bottom: 20px;
        }

        img {
            width: 100%;
            max-width: 800px;
            border-radius: 8px;
        }
    </style>
</head>

<body>
    <h1>Smart RC Car</h1>
    <img src="/video" alt="Caméra RC">
</body>
</html>
"""


# ==========================================================
# STREAM CAMÉRA
# ==========================================================

def generate_frames():
    encode_param = [
        int(cv2.IMWRITE_JPEG_QUALITY),
        JPEG_QUALITY,
    ]

    while not shutdown_event.is_set():

        if not camera_available:
            time.sleep(0.5)
            continue

        success, frame = camera.read()

        if not success:
            time.sleep(0.05)
            continue

        ret, buffer = cv2.imencode(
            ".jpg",
            frame,
            encode_param,
        )

        if not ret:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )


# ==========================================================
# PAGE WEB
# ==========================================================

@app.route("/")
def index():
    return render_template_string(
        html_page
    )


# ==========================================================
# VIDÉO
# ==========================================================

@app.route("/video")
def video():
    if not camera_available:
        return jsonify({
            "ok": False,
            "error": "Caméra indisponible",
        }), 503

    return Response(
        generate_frames(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        ),
    )


# ==========================================================
# STATUS
# ==========================================================

@app.route("/status")
def status():
    mode = (
        "auto"
        if drive_control.is_autopilot_enabled()
        else "manual"
    )

    return jsonify({
        "mode": mode,

        "camera": (
            "connected"
            if camera_available
            else "disconnected"
        ),

        "device": "/dev/video0",
        "resolution": f"{WIDTH}x{HEIGHT}",
        "fps": FPS,
        "jpeg_quality": JPEG_QUALITY,

        "battery": battery_sensor.lire_pourcentage(),

        "motors": drive_control.motor_state(),

        "manual": drive_control.manual_state(),

        "line_follower":
            line_auto.line_follower_state(),
    })


# ==========================================================
# CONTRÔLE MANUEL
# ==========================================================

@app.route("/control/press/<command>")
def control_press(command: str):
    if not drive_control.set_axis(
        command,
        True,
        source="manual",
    ):
        if drive_control.is_autopilot_enabled():
            return jsonify({
                "ok": False,
                "error": (
                    "Commande manuelle refusée : "
                    "le mode automatique est actif"
                ),
            }), 409

        return jsonify({
            "ok": False,
            "error": f"Commande inconnue : {command}",
        }), 404

    return jsonify({
        "ok": True,
        "action": "press",
        "command": command,
        "manual": drive_control.manual_state(),
        "motors": drive_control.motor_state(),
    })


@app.route("/control/release/<command>")
def control_release(command: str):
    if not drive_control.set_axis(
        command,
        False,
        source="manual",
    ):
        if drive_control.is_autopilot_enabled():
            return jsonify({
                "ok": False,
                "error": (
                    "Commande manuelle refusée : "
                    "le mode automatique est actif"
                ),
            }), 409

        return jsonify({
            "ok": False,
            "error": f"Commande inconnue : {command}",
        }), 404

    return jsonify({
        "ok": True,
        "action": "release",
        "command": command,
        "manual": drive_control.manual_state(),
        "motors": drive_control.motor_state(),
    })


# ==========================================================
# THROTTLE
# ==========================================================

@app.route("/control/throttle/<raw_value>")
def control_throttle(raw_value: str):
    try:
        percent = int(raw_value)

    except ValueError:
        return jsonify({
            "ok": False,
            "error": (
                "Valeur invalide, "
                "doit être un entier"
            ),
        }), 400

    if not -100 <= percent <= 100:
        return jsonify({
            "ok": False,
            "error": (
                "La valeur doit être "
                "entre -100 et 100"
            ),
        }), 400

    success = drive_control.set_throttle(
        percent / 100.0,
        source="manual",
    )

    if not success:
        return jsonify({
            "ok": False,
            "error": (
                "Commande manuelle refusée : "
                "le mode automatique est actif"
            ),
        }), 409

    return jsonify({
        "ok": True,
        "action": "throttle",
        "throttle": percent,
        "motors": drive_control.motor_state(),
    })


# ==========================================================
# STOP GLOBAL
# ==========================================================

@app.route("/control/stop")
def control_stop():
    drive_control.stop_all(
        disable_autopilot=True
    )

    return jsonify({
        "ok": True,
        "action": "stop",
        "mode": "manual",
        "motors": drive_control.motor_state(),
        "line_follower":
            line_auto.line_follower_state(),
    })


# ==========================================================
# AUTOPILOTE
# ==========================================================

@app.route("/control/autopilot/on")
def control_autopilot_on():
    drive_control.enable_auto_mode()

    return jsonify({
        "ok": True,
        "action": "autopilot_on",
        "mode": "auto",
        "line_follower":
            line_auto.line_follower_state(),
    })


@app.route("/control/autopilot/off")
def control_autopilot_off():
    drive_control.enable_manual_mode()

    return jsonify({
        "ok": True,
        "action": "autopilot_off",
        "mode": "manual",
        "line_follower":
            line_auto.line_follower_state(),
    })


# ==========================================================
# BASCULE DE MODE
# ==========================================================

@app.route("/switch/auto")
def switch_to_auto():
    drive_control.enable_auto_mode()

    return jsonify({
        "ok": True,
        "switching_to": "auto",
        "restart": False,
        "mode": "auto",
        "line_follower":
            line_auto.line_follower_state(),
    })


@app.route("/switch/manual")
def switch_to_manual():
    drive_control.enable_manual_mode()

    return jsonify({
        "ok": True,
        "switching_to": "manual",
        "restart": False,
        "mode": "manual",
        "line_follower":
            line_auto.line_follower_state(),
    })


# ==========================================================
# SERVEUR
# ==========================================================

def start_camera_server() -> None:
    print()
    print("==========================================")
    print("       SMART RC CAR — SERVEUR UNIFIÉ")
    print("==========================================")
    print()

    print(
        "Page web      : "
        "http://IP_DU_RASPBERRY:5000"
    )

    print(
        "État          : "
        "http://IP_DU_RASPBERRY:5000/status"
    )

    print(
        "Vidéo         : "
        "http://IP_DU_RASPBERRY:5000/video"
    )

    print()
    print("Switch auto   : /switch/auto")
    print("Switch manuel : /switch/manual")
    print()
    print("Contrôle manuel :")
    print("  /control/press/forward")
    print("  /control/release/forward")
    print("  /control/press/backward")
    print("  /control/press/left")
    print("  /control/press/right")
    print("  /control/throttle/50")
    print("  /control/stop")
    print()
    print("==========================================")
    print()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


# ==========================================================
# LANCEMENT
# ==========================================================

if __name__ == "__main__":
    line_thread = None

    try:
        # Démarrage en mode manuel.
        drive_control.enable_manual_mode()

        # Le thread reste vivant pendant toute l'exécution,
        # mais ne commande les moteurs qu'en mode AUTO.
        line_thread = threading.Thread(
            target=line_auto.line_follower_loop,
            args=(shutdown_event,),
            daemon=True,
            name="line-follower",
        )

        line_thread.start()

        print("Programme unifié lancé.")
        print("Mode initial : MANUEL")
        print("Ctrl+C pour arrêter.")

        start_camera_server()

    except KeyboardInterrupt:
        print("\nArrêt demandé.")

    finally:
        print("Nettoyage...")

        # 1. Demande l'arrêt du thread.
        shutdown_event.set()

        # 2. Attend que la boucle de suivi soit réellement terminée.
        if (
            line_thread is not None
            and line_thread.is_alive()
        ):
            line_thread.join(timeout=1.0)

        # 3. Libère les capteurs.
        line_auto.cleanup()

        # 4. Libère les moteurs.
        drive_control.cleanup()

        # 5. Libère la caméra.
        if camera.isOpened():
            camera.release()

        print(
            "Moteurs, capteurs et caméra libérés."
        )
