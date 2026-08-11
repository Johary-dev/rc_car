#!/usr/bin/env python3
"""
Serveur RC unifié.

Améliorations :
- manuel + automatique dans un seul processus ;
- lecture caméra dans UN SEUL thread ;
- clients vidéo servis depuis la dernière JPEG en mémoire ;
- lecture INA219 mise en cache (1 lecture/seconde) ;
- commandes manuelles reçues pendant AUTO ignorées avec HTTP 200 ;
- arrêt propre des threads avant libération des GPIO.

Lancement :
    python3 rc_unified.py
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import cv2
from flask import Flask, Response, jsonify, render_template_string

import drive_control
import line_auto
from batterie_ina219 import CapteurBatterie


# ==========================================================
# ÉTAT GLOBAL
# ==========================================================

shutdown_event = threading.Event()

battery_sensor = CapteurBatterie()


# ==========================================================
# CAMÉRA
# ==========================================================

CAMERA_INDEX = 0
WIDTH = 640
HEIGHT = 360
FPS = 20
JPEG_QUALITY = 60

CAMERA_RETRY_DELAY = 1.0

camera_condition = threading.Condition()

camera_available = False
camera_error: Optional[str] = None

latest_jpeg: Optional[bytes] = None
latest_frame_id = 0


def _configure_camera(camera) -> None:
    camera.set(
        cv2.CAP_PROP_FOURCC,
        cv2.VideoWriter_fourcc(*"MJPG"),
    )
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    camera.set(cv2.CAP_PROP_FPS, FPS)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)


def camera_loop(
    stop_event: threading.Event,
) -> None:
    """
    Seul ce thread appelle camera.read().
    Les clients /video lisent uniquement latest_jpeg.
    """
    global camera_available
    global camera_error
    global latest_jpeg
    global latest_frame_id

    encode_param = [
        int(cv2.IMWRITE_JPEG_QUALITY),
        JPEG_QUALITY,
    ]

    while not stop_event.is_set():
        camera = cv2.VideoCapture(
            CAMERA_INDEX,
            cv2.CAP_V4L2,
        )

        if not camera.isOpened():
            with camera_condition:
                camera_available = False
                camera_error = "Caméra /dev/video0 indisponible"
                camera_condition.notify_all()

            camera.release()
            stop_event.wait(CAMERA_RETRY_DELAY)
            continue

        _configure_camera(camera)

        with camera_condition:
            camera_available = True
            camera_error = None
            camera_condition.notify_all()

        print("Caméra connectée.")

        while not stop_event.is_set():
            success, frame = camera.read()

            if not success:
                with camera_condition:
                    camera_available = False
                    camera_error = "Lecture caméra interrompue"
                    camera_condition.notify_all()

                print(
                    "Lecture caméra interrompue "
                    "— tentative de reconnexion."
                )
                break

            ret, buffer = cv2.imencode(
                ".jpg",
                frame,
                encode_param,
            )

            if not ret:
                continue

            jpeg = buffer.tobytes()

            with camera_condition:
                latest_jpeg = jpeg
                latest_frame_id += 1
                camera_available = True
                camera_error = None
                camera_condition.notify_all()

        camera.release()

        if not stop_event.is_set():
            stop_event.wait(CAMERA_RETRY_DELAY)

    with camera_condition:
        camera_available = False
        camera_condition.notify_all()

    print("Thread caméra arrêté.")


def generate_frames():
    """
    Stream MJPEG depuis l'image encodée par camera_loop().
    """
    last_frame_id = -1

    while not shutdown_event.is_set():
        with camera_condition:
            camera_condition.wait_for(
                lambda: (
                    shutdown_event.is_set()
                    or latest_frame_id != last_frame_id
                ),
                timeout=2.0,
            )

            if shutdown_event.is_set():
                break

            if (
                latest_jpeg is None
                or latest_frame_id == last_frame_id
            ):
                continue

            frame = latest_jpeg
            last_frame_id = latest_frame_id

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame
            + b"\r\n"
        )


# ==========================================================
# BATTERIE INA219 - CACHE
# ==========================================================

BATTERY_READ_INTERVAL = 1.0

battery_lock = threading.Lock()

battery_percentage: Optional[int] = None
battery_error: Optional[str] = None
battery_last_update: Optional[float] = None


def update_battery_once() -> None:
    global battery_percentage
    global battery_error
    global battery_last_update

    try:
        value = battery_sensor.lire_pourcentage()

        with battery_lock:
            battery_percentage = int(value)
            battery_error = None
            battery_last_update = time.time()

    except Exception as exc:
        with battery_lock:
            battery_error = str(exc)
            battery_last_update = time.time()


def battery_loop(
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        update_battery_once()
        stop_event.wait(BATTERY_READ_INTERVAL)

    print("Thread batterie arrêté.")


def battery_state() -> dict:
    with battery_lock:
        return {
            "percentage": battery_percentage,
            "error": battery_error,
            "last_update": battery_last_update,
        }


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

        img {
            width: 100%;
            max-width: 800px;
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
# ROUTES GÉNÉRALES
# ==========================================================

@app.route("/")
def index():
    return render_template_string(html_page)


@app.route("/video")
def video():
    with camera_condition:
        available = camera_available
        has_frame = latest_jpeg is not None
        error = camera_error

    if not available and not has_frame:
        return jsonify({
            "ok": False,
            "error": error or "Caméra indisponible",
        }), 503

    return Response(
        generate_frames(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        ),
    )


@app.route("/status")
def status():
    mode = (
        "auto"
        if drive_control.is_autopilot_enabled()
        else "manual"
    )

    with camera_condition:
        current_camera_available = camera_available
        current_camera_error = camera_error

    battery = battery_state()

    return jsonify({
        "ok": True,
        "mode": mode,

        # Compatibilité avec l'application mobile :
        # battery reste une valeur numérique.
        "battery": battery["percentage"],
        "battery_error": battery["error"],

        "camera": (
            "connected"
            if current_camera_available
            else "disconnected"
        ),
        "camera_error": current_camera_error,

        "device": "/dev/video0",
        "resolution": f"{WIDTH}x{HEIGHT}",
        "fps": FPS,
        "jpeg_quality": JPEG_QUALITY,

        "motors": drive_control.motor_state(),
        "manual": drive_control.manual_state(),

        "line_follower":
            line_auto.line_follower_state(),
    })


# ==========================================================
# COMMANDES MANUELLES REÇUES PENDANT AUTO
# ==========================================================

def ignored_manual_command_response(
    action: str,
    command=None,
):
    """
    Une commande manuelle résiduelle pendant AUTO n'est pas
    considérée comme une erreur réseau.

    HTTP 200 évite que l'application interprète ce cas normal
    comme une déconnexion du serveur.
    """
    payload = {
        "ok": True,
        "accepted": False,
        "ignored": True,
        "reason": "auto_mode_active",
        "action": action,
        "mode": "auto",
    }

    if command is not None:
        payload["command"] = command

    return jsonify(payload), 200


# ==========================================================
# CONTRÔLE MANUEL
# ==========================================================

@app.route("/control/press/<command>")
def control_press(command: str):
    if command not in drive_control.VALID_AXES:
        return jsonify({
            "ok": False,
            "error": f"Commande inconnue : {command}",
        }), 404

    if drive_control.is_autopilot_enabled():
        return ignored_manual_command_response(
            "press",
            command,
        )

    success = drive_control.set_axis(
        command,
        True,
        source="manual",
    )

    if not success:
        if drive_control.is_autopilot_enabled():
            return ignored_manual_command_response(
                "press",
                command,
            )

        return jsonify({
            "ok": False,
            "error": "Commande refusée",
        }), 409

    return jsonify({
        "ok": True,
        "accepted": True,
        "action": "press",
        "command": command,
        "manual": drive_control.manual_state(),
        "motors": drive_control.motor_state(),
    })


@app.route("/control/release/<command>")
def control_release(command: str):
    if command not in drive_control.VALID_AXES:
        return jsonify({
            "ok": False,
            "error": f"Commande inconnue : {command}",
        }), 404

    if drive_control.is_autopilot_enabled():
        return ignored_manual_command_response(
            "release",
            command,
        )

    success = drive_control.set_axis(
        command,
        False,
        source="manual",
    )

    if not success:
        if drive_control.is_autopilot_enabled():
            return ignored_manual_command_response(
                "release",
                command,
            )

        return jsonify({
            "ok": False,
            "error": "Commande refusée",
        }), 409

    return jsonify({
        "ok": True,
        "accepted": True,
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

    if drive_control.is_autopilot_enabled():
        return ignored_manual_command_response(
            "throttle"
        )

    success = drive_control.set_throttle(
        percent / 100.0,
        source="manual",
    )

    if not success:
        if drive_control.is_autopilot_enabled():
            return ignored_manual_command_response(
                "throttle"
            )

        return jsonify({
            "ok": False,
            "error": "Throttle refusé",
        }), 409

    return jsonify({
        "ok": True,
        "accepted": True,
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
# AUTOPILOTE / SWITCH
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

def start_server() -> None:
    print()
    print("==========================================")
    print("       SMART RC CAR — SERVEUR UNIFIÉ")
    print("==========================================")
    print()
    print("Page   : http://IP_DU_RASPBERRY:5000")
    print("Status : http://IP_DU_RASPBERRY:5000/status")
    print("Vidéo  : http://IP_DU_RASPBERRY:5000/video")
    print()
    print("Auto   : /switch/auto")
    print("Manuel : /switch/manual")
    print("Stop   : /control/stop")
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
    camera_thread = None
    battery_thread = None

    try:
        drive_control.enable_manual_mode()

        # Première lecture batterie avant le serveur.
        update_battery_once()

        line_thread = threading.Thread(
            target=line_auto.line_follower_loop,
            args=(shutdown_event,),
            daemon=True,
            name="line-follower",
        )

        camera_thread = threading.Thread(
            target=camera_loop,
            args=(shutdown_event,),
            daemon=True,
            name="camera-reader",
        )

        battery_thread = threading.Thread(
            target=battery_loop,
            args=(shutdown_event,),
            daemon=True,
            name="battery-reader",
        )

        line_thread.start()
        camera_thread.start()
        battery_thread.start()

        print("Programme unifié lancé.")
        print("Mode initial : MANUEL")
        print("Ctrl+C pour arrêter.")

        start_server()

    except KeyboardInterrupt:
        print("\nArrêt demandé.")

    finally:
        print("Nettoyage...")

        shutdown_event.set()

        # Réveille les clients vidéo qui attendent une frame.
        with camera_condition:
            camera_condition.notify_all()

        for thread in (
            line_thread,
            camera_thread,
            battery_thread,
        ):
            if (
                thread is not None
                and thread.is_alive()
            ):
                thread.join(timeout=2.0)

        line_auto.cleanup()
        drive_control.cleanup()

        print(
            "Moteurs, capteurs, caméra "
            "et threads libérés."
        )
