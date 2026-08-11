"""
Suivi de ligne noire (capteurs FC-51).

Ce module n'ouvre AUCUNE broche moteur : il lit les capteurs et envoie
les directions à drive_control.set_axis — la même fonction que l'API HTTP.
"""

from __future__ import annotations

import threading
from typing import Optional, Tuple

from gpiozero import DigitalInputDevice

import drive_control

# Branchements FC-51 (inversés physiquement sur le câblage actuel)
LEFT_SENSOR_PIN = 26
RIGHT_SENSOR_PIN = 27
LEFT_SENSOR_PHYSICAL_PIN = 37
RIGHT_SENSOR_PHYSICAL_PIN = 13

# 1 = noir détecté. Passer à 0 si ton câblage est inversé.
LINE_ACTIVE_STATE = 1

FORWARD_SPEED = 0.37
TURN_SPEED = 0.4
LINE_LOOP_DELAY = 0.02

left_sensor = DigitalInputDevice(LEFT_SENSOR_PIN, pull_up=False)
right_sensor = DigitalInputDevice(RIGHT_SENSOR_PIN, pull_up=False)

line_state_lock = threading.Lock()
last_line_action = "initialisation"
last_left_value = None
last_right_value = None

# Dernière commande publiée — évite de spammer set_axis à chaque tick.
_last_published: Optional[Tuple[bool, bool, bool, float]] = None


def sensor_detects_line(value: Optional[int]) -> Optional[bool]:
    if value is None:
        return None
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


def _publish_directions(
    *,
    forward: bool,
    left: bool,
    right: bool,
    speed: float,
) -> None:
    """
    Envoie les directions via la même API que le mobile (set_axis).
    source="auto" → ne désactive pas l'autopilote.
    """
    global _last_published

    command = (forward, left, right, speed)
    if command == _last_published:
        return
    _last_published = command

    # Ordre : virages d'abord, puis avance (fixe le throttle final).
    drive_control.set_axis("backward", False, source="auto")
    drive_control.set_axis("left", left, source="auto")
    drive_control.set_axis("right", right, source="auto")
    drive_control.set_axis("forward", forward, source="auto", speed=speed)


def line_follower_loop(shutdown_event: threading.Event) -> None:
    """
    Boucle de détection :

    - aucun / les deux capteurs voient le noir → avancer
    - capteur droit seulement → avancer + tourner à droite
    - capteur gauche seulement → avancer + tourner à gauche
    """
    global last_line_action, _last_published

    print("Suivi de ligne prêt (en attente d'activation autopilote)")
    print(f"FC-51 gauche : GPIO{LEFT_SENSOR_PIN}, pin physique {LEFT_SENSOR_PHYSICAL_PIN}")
    print(f"FC-51 droit  : GPIO{RIGHT_SENSOR_PIN}, pin physique {RIGHT_SENSOR_PHYSICAL_PIN}")
    print(f"État configuré pour le noir : {LINE_ACTIVE_STATE}")

    previous_action = None

    while not shutdown_event.is_set():
        if not drive_control.is_autopilot_enabled():
            if _last_published is not None:
                _last_published = None
            shutdown_event.wait(LINE_LOOP_DELAY)
            continue

        sensors = read_line_state()
        left_detected = sensors["left_detected"]
        right_detected = sensors["right_detected"]

        if left_detected and right_detected:
            action = "avancer"
            _publish_directions(forward=True, left=False, right=False, speed=FORWARD_SPEED)

        elif right_detected and not left_detected:
            action = "tourner_droite"
            _publish_directions(forward=True, left=False, right=True, speed=TURN_SPEED)

        elif left_detected and not right_detected:
            action = "tourner_gauche"
            _publish_directions(forward=True, left=True, right=False, speed=TURN_SPEED)

        else:
            # Aucun noir : ligne au milieu → avancer
            action = "avancer_ligne_au_milieu"
            _publish_directions(forward=True, left=False, right=False, speed=FORWARD_SPEED)

        with line_state_lock:
            last_line_action = action

        if action != previous_action:
            print(
                f"FC51 gauche={sensors['left_value']} | "
                f"droite={sensors['right_value']} | action={action}"
            )
            previous_action = action

        shutdown_event.wait(LINE_LOOP_DELAY)

    drive_control.clear_directions(stop=True)


def line_follower_state() -> dict:
    with line_state_lock:
        left_value = last_left_value
        right_value = last_right_value
        action = last_line_action

    return {
        "enabled": drive_control.is_autopilot_enabled(),
        "line_active_state": LINE_ACTIVE_STATE,
        "left": {
            "gpio": LEFT_SENSOR_PIN,
            "physical_pin": LEFT_SENSOR_PHYSICAL_PIN,
            "value": left_value,
            "line_detected": sensor_detects_line(left_value),
        },
        "right": {
            "gpio": RIGHT_SENSOR_PIN,
            "physical_pin": RIGHT_SENSOR_PHYSICAL_PIN,
            "value": right_value,
            "line_detected": sensor_detects_line(right_value),
        },
        "action": action,
    }


def cleanup() -> None:
    left_sensor.close()
    right_sensor.close()
