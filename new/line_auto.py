#!/usr/bin/env python3
"""
Suivi de ligne noire avec deux capteurs FC-51.

Ce module n'ouvre AUCUNE broche moteur.

Il lit uniquement les FC-51 et transmet les consignes de conduite
à drive_control.set_motion().

Architecture :

    FC-51
      |
      v
    line_auto.py
      |
      | set_motion(..., source="auto")
      v
    drive_control.py
      |
      v
    moteurs
"""

from __future__ import annotations

import threading
from typing import Optional

from gpiozero import DigitalInputDevice

import drive_control


# ==========================================================
# CONFIGURATION FC-51
# ==========================================================

# Câblage actuel :
LEFT_SENSOR_PIN = 26
RIGHT_SENSOR_PIN = 27

LEFT_SENSOR_PHYSICAL_PIN = 37
RIGHT_SENSOR_PHYSICAL_PIN = 13

# 1 = noir détecté.
# Mettre 0 si la logique électrique de tes FC-51 est inversée.
LINE_ACTIVE_STATE = 1


# ==========================================================
# PARAMÈTRES DE CONDUITE
# ==========================================================

FORWARD_SPEED = 0.37
TURN_SPEED = 0.40

# 20 ms = environ 50 lectures par seconde.
LINE_LOOP_DELAY = 0.02


# ==========================================================
# CAPTEURS
# ==========================================================

left_sensor = DigitalInputDevice(
    LEFT_SENSOR_PIN,
    pull_up=False,
)

right_sensor = DigitalInputDevice(
    RIGHT_SENSOR_PIN,
    pull_up=False,
)


# ==========================================================
# ÉTAT INTERNE
# ==========================================================

line_state_lock = threading.Lock()

last_line_action = "initialisation"
last_left_value: Optional[int] = None
last_right_value: Optional[int] = None


# ==========================================================
# UTILITAIRES
# ==========================================================

def sensor_detects_line(
    value: Optional[int],
) -> Optional[bool]:
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


# ==========================================================
# PUBLICATION ATOMIQUE
# ==========================================================

def _publish_directions(
    *,
    forward: bool,
    left: bool,
    right: bool,
    speed: float,
) -> None:
    """
    Envoie une seule consigne complète à drive_control.

    drive_control effectue lui-même la vérification finale du mode.
    """
    drive_control.set_motion(
        speed if forward else 0.0,
        left=left,
        right=right,
        source="auto",
    )


# ==========================================================
# BOUCLE DE SUIVI
# ==========================================================

def line_follower_loop(
    shutdown_event: threading.Event,
) -> None:
    """
    Logique actuelle :

        gauche=0, droite=0
            -> ligne entre les deux capteurs
            -> avancer

        gauche=1, droite=1
            -> les deux voient le noir
            -> avancer

        gauche=0, droite=1
            -> corriger à droite

        gauche=1, droite=0
            -> corriger à gauche
    """
    global last_line_action

    print()
    print("Suivi de ligne prêt (en attente d'activation autopilote)")
    print(
        f"FC-51 gauche : GPIO{LEFT_SENSOR_PIN}, "
        f"pin physique {LEFT_SENSOR_PHYSICAL_PIN}"
    )
    print(
        f"FC-51 droit  : GPIO{RIGHT_SENSOR_PIN}, "
        f"pin physique {RIGHT_SENSOR_PHYSICAL_PIN}"
    )
    print(f"État configuré pour le noir : {LINE_ACTIVE_STATE}")
    print()

    previous_action: Optional[str] = None

    while not shutdown_event.is_set():

        # --------------------------------------------------
        # MODE MANUEL : aucune commande moteur
        # --------------------------------------------------
        if not drive_control.is_autopilot_enabled():
            with line_state_lock:
                last_line_action = "inactif_mode_manuel"

            previous_action = None
            shutdown_event.wait(LINE_LOOP_DELAY)
            continue

        # --------------------------------------------------
        # LECTURE CAPTEURS
        # --------------------------------------------------
        sensors = read_line_state()

        left_detected = sensors["left_detected"]
        right_detected = sensors["right_detected"]

        # --------------------------------------------------
        # DÉCISION
        # --------------------------------------------------
        if left_detected and right_detected:
            action = "avancer"

            _publish_directions(
                forward=True,
                left=False,
                right=False,
                speed=FORWARD_SPEED,
            )

        elif right_detected and not left_detected:
            action = "tourner_droite"

            _publish_directions(
                forward=True,
                left=False,
                right=True,
                speed=TURN_SPEED,
            )

        elif left_detected and not right_detected:
            action = "tourner_gauche"

            _publish_directions(
                forward=True,
                left=True,
                right=False,
                speed=TURN_SPEED,
            )

        else:
            # Aucun capteur ne voit le noir :
            # dans ce montage, la ligne est considérée au milieu.
            action = "avancer_ligne_au_milieu"

            _publish_directions(
                forward=True,
                left=False,
                right=False,
                speed=FORWARD_SPEED,
            )

        # --------------------------------------------------
        # MÉMORISATION
        # --------------------------------------------------
        with line_state_lock:
            last_line_action = action

        # --------------------------------------------------
        # LOG UNIQUEMENT SI L'ACTION CHANGE
        # --------------------------------------------------
        if action != previous_action:
            print(
                f"FC51 gauche={sensors['left_value']} | "
                f"droite={sensors['right_value']} | "
                f"action={action}"
            )
            previous_action = action

        shutdown_event.wait(LINE_LOOP_DELAY)

    # À la sortie du thread, on demande un arrêt moteur.
    # Pendant l'arrêt global du programme, ceci est sans danger.
    drive_control.clear_directions(stop=True)

    print("Thread suivi de ligne arrêté.")


# ==========================================================
# ÉTAT POUR /status
# ==========================================================

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


# ==========================================================
# CLEANUP
# ==========================================================

def cleanup() -> None:
    left_sensor.close()
    right_sensor.close()

    print("FC-51 libérés.")
