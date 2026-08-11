import threading
import time

import cv2
from flask import Flask, Response, jsonify, render_template_string
from gpiozero import DigitalInputDevice, Motor, OutputDevice, PWMOutputDevice

# ==========================================================
# CONFIGURATION DES MOTEURS
# ==========================================================

VALID_AXES = {"forward", "backward", "left", "right"}

left_motor = Motor(forward=17, backward=22)
left_pwm = PWMOutputDevice(18)

right_motor = Motor(forward=23, backward=24)
right_pwm = PWMOutputDevice(13)

motor_lock = threading.Lock()
manual_state_lock = threading.Lock()

throttle = 0.0
is_left = False
is_right = False

current_left_speed = 0.0
current_right_speed = 0.0


# ==========================================================
# CONFIGURATION DES DEUX FC-51
# ==========================================================

# Les branchements physiques ont été inversés :
# capteur gauche  -> pin physique 29 = GPIO5
# capteur droit   -> pin physique 37 = GPIO26
LEFT_SENSOR_PIN = 26
RIGHT_SENSOR_PIN = 27

LEFT_SENSOR_PHYSICAL_PIN = 37
RIGHT_SENSOR_PHYSICAL_PIN = 13

left_sensor = DigitalInputDevice(LEFT_SENSOR_PIN, pull_up=False)
right_sensor = DigitalInputDevice(RIGHT_SENSOR_PIN, pull_up=False)

# Valeur retournée lorsque le capteur voit la ligne noire.
# Commence par 1. Si ton test indique que le noir produit 0,
# remplace simplement 1 par 0.
LINE_ACTIVE_STATE = 1

FORWARD_SPEED = 0.37
TURN_SPEED = 0.4
LINE_LOOP_DELAY = 0.02

line_state_lock = threading.Lock()
autopilot_lock = threading.Lock()
shutdown_event = threading.Event()

autopilot_enabled = True
last_line_action = "initialisation"
last_left_value = None
last_right_value = None


# ==========================================================
# CONFIGURATION DES CLIGNOTANTS
# ==========================================================

BLINKER_LEFT_PIN = 25

# GPIO26 est maintenant utilisé par le FC-51 gauche.
# Le relais droit doit être déplacé vers GPIO20, pin physique 38.
BLINKER_RIGHT_PIN = 20
BLINKER_INTERVAL = 0.5

blinker_left_relay = OutputDevice(
    BLINKER_LEFT_PIN,
    active_high=False,
    initial_value=False,
)
blinker_right_relay = OutputDevice(
    BLINKER_RIGHT_PIN,
    active_high=False,
    initial_value=False,
)

blinker_lock = threading.Lock()
blinker_stop_event = threading.Event()
blinker_thread = None

blinker_left_active = False
blinker_right_active = False


# ==========================================================
# FONCTIONS MOTEURS
# ==========================================================


def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def drive_side(motor, pwm, speed: float):
    """
    speed > 0 : avancer
    speed < 0 : reculer
    speed = 0 : arrêter
    """
    speed = clamp(speed)
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
    """Commande directement les vitesses des deux côtés."""
    global current_left_speed, current_right_speed

    left_speed = clamp(left_speed)
    right_speed = clamp(right_speed)

    with motor_lock:
        drive_side(left_motor, left_pwm, left_speed)
        drive_side(right_motor, right_pwm, right_speed)

        current_left_speed = left_speed
        current_right_speed = right_speed


def stop_motors():
    set_motor_speeds(0.0, 0.0)


def motor_state() -> dict:
    with motor_lock:
        return {
            "left_speed": current_left_speed,
            "right_speed": current_right_speed,
        }


# ==========================================================
# PILOTAGE AUTOMATIQUE PAR LES FC-51
# ==========================================================


def set_autopilot(enabled: bool, stop_when_disabled: bool = True):
    global autopilot_enabled

    with autopilot_lock:
        autopilot_enabled = enabled

    if not enabled and stop_when_disabled:
        stop_motors()


def is_autopilot_enabled() -> bool:
    with autopilot_lock:
        return autopilot_enabled


def sensor_detects_line(value: int) -> bool:
    return value == LINE_ACTIVE_STATE


def read_line_state() -> dict:
    global last_left_value, last_right_value

    left_value = int(left_sensor.value)
    right_value = int(right_sensor.value)

    with line_state_lock:
        last_left_value = left_value
        last_right_value = right_value

    return {
        "left_value": left_value,
        "right_value": right_value,
        "left_detected": sensor_detects_line(left_value),
        "right_detected": sensor_detects_line(right_value),
    }


def line_follower_loop():
    """
    Logique demandée :

    - les deux capteurs voient le noir : avancer ;
    - capteur gauche seulement : côté droit en avant et côté gauche en arrière ;
    - capteur droit seulement : côté gauche en avant et côté droit en arrière ;
    - aucun capteur ne voit le noir : avancer, car la ligne est au milieu.
    """
    global last_line_action

    print("Suivi de ligne automatique activé")
    print(
        f"FC-51 gauche : GPIO{LEFT_SENSOR_PIN}, "
        f"pin physique {LEFT_SENSOR_PHYSICAL_PIN}"
    )
    print(
        f"FC-51 droit  : GPIO{RIGHT_SENSOR_PIN}, "
        f"pin physique {RIGHT_SENSOR_PHYSICAL_PIN}"
    )
    print(f"État configuré pour le noir : {LINE_ACTIVE_STATE}")

    previous_action = None

    while not shutdown_event.is_set():
        if not is_autopilot_enabled():
            shutdown_event.wait(LINE_LOOP_DELAY)
            continue

        sensors = read_line_state()
        left_detected = sensors["left_detected"]
        right_detected = sensors["right_detected"]

        if left_detected and right_detected:
            action = "avancer"
            set_motor_speeds(FORWARD_SPEED, FORWARD_SPEED)

        elif right_detected and not left_detected:
            action = "pivot_droite"
            # Ligne détectée à droite :
            # roues gauches en avant, roues droites en arrière.
            set_motor_speeds(TURN_SPEED, -TURN_SPEED)

        elif left_detected and not right_detected:
            action = "pivot_gauche"
            # Ligne détectée à gauche :
            # roues gauches en arrière, roues droites en avant.
            set_motor_speeds(-TURN_SPEED, TURN_SPEED)

        else:
            # Aucun capteur ne voit le noir : la ligne est entre les capteurs.
            action = "avancer_ligne_au_milieu"
            set_motor_speeds(FORWARD_SPEED, FORWARD_SPEED)

        with line_state_lock:
            last_line_action = action

        if action != previous_action:
            print(
                f"FC51 gauche={sensors['left_value']} | "
                f"droite={sensors['right_value']} | action={action}"
            )
            previous_action = action

        shutdown_event.wait(LINE_LOOP_DELAY)

    stop_motors()


def line_follower_state() -> dict:
    with line_state_lock:
        left_value = last_left_value
        right_value = last_right_value
        action = last_line_action

    return {
        "enabled": is_autopilot_enabled(),
        "line_active_state": LINE_ACTIVE_STATE,
        "left": {
            "gpio": LEFT_SENSOR_PIN,
            "physical_pin": LEFT_SENSOR_PHYSICAL_PIN,
            "value": left_value,
            "line_detected": (
                sensor_detects_line(left_value)
                if left_value is not None
                else None
            ),
        },
        "right": {
            "gpio": RIGHT_SENSOR_PIN,
            "physical_pin": RIGHT_SENSOR_PHYSICAL_PIN,
            "value": right_value,
            "line_detected": (
                sensor_detects_line(right_value)
                if right_value is not None
                else None
            ),
        },
        "action": action,
    }


# ==========================================================
# CONTRÔLE MANUEL HTTP
# ==========================================================


def apply_manual_motors():
    global throttle, is_left, is_right

    steer = 0.0

    if is_left:
        steer = -1.0
    elif is_right:
        steer = 1.0

    speed_limit = abs(throttle)
    effective_steer = steer * speed_limit

    left_speed = clamp(throttle + effective_steer, -speed_limit, speed_limit)
    right_speed = clamp(throttle - effective_steer, -speed_limit, speed_limit)

    set_motor_speeds(left_speed, right_speed)


def set_axis(axis: str, active: bool) -> bool:
    global throttle, is_left, is_right

    if axis not in VALID_AXES:
        return False

    # Une commande manuelle désactive l'autopilote.
    set_autopilot(False, stop_when_disabled=False)

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

    set_autopilot(False, stop_when_disabled=False)

    with manual_state_lock:
        throttle = clamp(value)
        apply_manual_motors()

    return True


def stop_all(disable_autopilot: bool = True):
    global throttle, is_left, is_right

    if disable_autopilot:
        set_autopilot(False, stop_when_disabled=False)

    with manual_state_lock:
        throttle = 0.0
        is_left = False
        is_right = False

    stop_motors()


def manual_state() -> dict:
    with manual_state_lock:
        return {
            "throttle": throttle,
            "left": is_left,
            "right": is_right,
        }


# ==========================================================
# CLIGNOTANTS
# ==========================================================


def _set_blinker_outputs(is_on: bool):
    if is_on and blinker_left_active:
        blinker_left_relay.on()
    else:
        blinker_left_relay.off()

    if is_on and blinker_right_active:
        blinker_right_relay.on()
    else:
        blinker_right_relay.off()


def _blinker_loop():
    while not blinker_stop_event.is_set():
        with blinker_lock:
            if not blinker_left_active and not blinker_right_active:
                break

            _set_blinker_outputs(True)

        if blinker_stop_event.wait(BLINKER_INTERVAL):
            break

        with blinker_lock:
            _set_blinker_outputs(False)

        if blinker_stop_event.wait(BLINKER_INTERVAL):
            break

    with blinker_lock:
        blinker_left_relay.off()
        blinker_right_relay.off()


def _sync_blinker_thread():
    global blinker_thread

    if blinker_left_active or blinker_right_active:
        blinker_stop_event.clear()

        if blinker_thread is None or not blinker_thread.is_alive():
            blinker_thread = threading.Thread(
                target=_blinker_loop,
                daemon=True,
            )
            blinker_thread.start()
    else:
        blinker_stop_event.set()


def toggle_blinker(side: str) -> bool:
    global blinker_left_active, blinker_right_active

    if side not in {"left", "right"}:
        return False

    with blinker_lock:
        if side == "left":
            blinker_left_active = not blinker_left_active
            if blinker_left_active:
                blinker_right_active = False
        else:
            blinker_right_active = not blinker_right_active
            if blinker_right_active:
                blinker_left_active = False

        _sync_blinker_thread()

    return True


def stop_blinkers():
    global blinker_left_active, blinker_right_active

    with blinker_lock:
        blinker_left_active = False
        blinker_right_active = False
        _sync_blinker_thread()


def blinker_state() -> dict:
    with blinker_lock:
        return {
            "left": blinker_left_active,
            "right": blinker_right_active,
        }


# ==========================================================
# CAMERA ET SERVEUR FLASK
# ==========================================================

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

camera_available = camera.isOpened()

if not camera_available:
    print("Attention : impossible d'ouvrir la caméra /dev/video0")
    print("Le suivi de ligne peut tout de même fonctionner.")


html_page = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Voiture RC</title>
    <style>
        body {
            background: #111;
            color: white;
            font-family: Arial, sans-serif;
            text-align: center;
        }

        img {
            width: 90%;
            max-width: 900px;
            border: 3px solid white;
            border-radius: 10px;
        }

        .info {
            margin: 15px;
            color: #ccc;
        }
    </style>
</head>
<body>
    <h1>Voiture RC — suivi de ligne</h1>
    <img src="/video" alt="Flux caméra">
    <div class="info">
        État complet disponible sur <code>/status</code>
    </div>
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
            print("Erreur : image non lue depuis la caméra")
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
        return jsonify({
            "ok": False,
            "error": "Caméra indisponible",
        }), 503

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/status")
def status():
    return jsonify({
        "camera": "connected" if camera_available else "disconnected",
        "device": "/dev/video0",
        "resolution": f"{WIDTH}x{HEIGHT}",
        "fps": FPS,
        "motors": motor_state(),
        "manual": manual_state(),
        "line_follower": line_follower_state(),
        "blinkers": blinker_state(),
    })


@app.route("/control/autopilot/on")
def control_autopilot_on():
    global throttle, is_left, is_right

    with manual_state_lock:
        throttle = 0.0
        is_left = False
        is_right = False

    set_autopilot(True, stop_when_disabled=False)

    return jsonify({
        "ok": True,
        "action": "autopilot_on",
        "line_follower": line_follower_state(),
    })


@app.route("/control/autopilot/off")
def control_autopilot_off():
    set_autopilot(False, stop_when_disabled=True)

    return jsonify({
        "ok": True,
        "action": "autopilot_off",
        "line_follower": line_follower_state(),
    })


@app.route("/control/press/<command>")
def control_press(command: str):
    if not set_axis(command, True):
        return jsonify({
            "ok": False,
            "error": f"Commande inconnue : {command}",
        }), 404

    return jsonify({
        "ok": True,
        "action": "press",
        "command": command,
        "manual": manual_state(),
        "motors": motor_state(),
    })


@app.route("/control/release/<command>")
def control_release(command: str):
    if not set_axis(command, False):
        return jsonify({
            "ok": False,
            "error": f"Commande inconnue : {command}",
        }), 404

    return jsonify({
        "ok": True,
        "action": "release",
        "command": command,
        "manual": manual_state(),
        "motors": motor_state(),
    })


@app.route("/control/stop")
def control_stop():
    stop_all(disable_autopilot=True)

    return jsonify({
        "ok": True,
        "action": "stop",
        "motors": motor_state(),
        "line_follower": line_follower_state(),
    })


@app.route("/control/throttle/<raw_value>")
def control_throttle(raw_value: str):
    try:
        percent = int(raw_value)
    except ValueError:
        return jsonify({
            "ok": False,
            "error": "Valeur invalide, doit être un entier",
        }), 400

    if not -100 <= percent <= 100:
        return jsonify({
            "ok": False,
            "error": "La valeur doit être entre -100 et 100",
        }), 400

    set_throttle(percent / 100.0)

    return jsonify({
        "ok": True,
        "action": "throttle",
        "throttle": percent,
        "motors": motor_state(),
    })


@app.route("/control/blinker/<side>/toggle")
def control_blinker_toggle(side: str):
    if not toggle_blinker(side):
        return jsonify({
            "ok": False,
            "error": f"Clignotant inconnu : {side}",
        }), 404

    return jsonify({
        "ok": True,
        "action": "blinker_toggle",
        "side": side,
        "blinkers": blinker_state(),
    })


@app.route("/control/blinker/off")
def control_blinker_off():
    stop_blinkers()

    return jsonify({
        "ok": True,
        "action": "blinker_off",
        "blinkers": blinker_state(),
    })


def start_camera_server():
    print("Serveur RC Camera démarré")
    print("Page web        : http://IP_DU_RASPBERRY:5000")
    print("État            : http://IP_DU_RASPBERRY:5000/status")
    print("Autopilote ON   : /control/autopilot/on")
    print("Autopilote OFF  : /control/autopilot/off")
    print("Arrêt            : /control/stop")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


# ==========================================================
# LANCEMENT DU PROGRAMME
# ==========================================================

if __name__ == "__main__":
    try:
        camera_thread = threading.Thread(
            target=start_camera_server,
            daemon=True,
        )
        camera_thread.start()

        line_thread = threading.Thread(
            target=line_follower_loop,
            daemon=True,
        )
        line_thread.start()

        print("Programme lancé en mode automatique.")
        print("Ctrl+C pour arrêter complètement.")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nArrêt demandé")

    finally:
        shutdown_event.set()
        stop_all(disable_autopilot=True)
        stop_blinkers()

        if camera_available:
            camera.release()

        left_sensor.close()
        right_sensor.close()

        blinker_left_relay.close()
        blinker_right_relay.close()

        left_pwm.close()
        right_pwm.close()
        left_motor.close()
        right_motor.close()

        print("Moteurs arrêtés, capteurs fermés et caméra libérée")