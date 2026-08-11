#!/usr/bin/env python3
"""
Suivi de ligne noire avec deux FC-51.

Ce module ne contrôle directement AUCUNE broche moteur.
Il lit les capteurs puis transmet des vitesses gauche/droite signées
à drive_control.

Stratégie :
    ligne au milieu / deux capteurs identiques -> avancer

    capteur gauche seul sur noir :
        moteur gauche -> arrière
        moteur droit  -> avant
        => pivot gauche

    capteur droit seul sur noir :
        moteur gauche -> avant
        moteur droit  -> arrière
        => pivot droite

Un filtre majoritaire réduit les oscillations 0/1 dues au bruit.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Optional

from gpiozero import DigitalInputDevice

import drive_control


# ==========================================================
# CONFIGURATION FC-51
# ==========================================================

LEFT_SENSOR_PIN = 26
RIGHT_SENSOR_PIN = 27

LEFT_SENSOR_PHYSICAL_PIN = 37
RIGHT_SENSOR_PHYSICAL_PIN = 13

# 1 = noir détecté.
# Mettre 0 si la logique de tes capteurs est inversée.
LINE_ACTIVE_STATE = 1


# ==========================================================
# PARAMÈTRES DE CONDUITE
# ==========================================================

STRAIGHT_SPEED = 0.37

# Pivot sur place.
# Commence à 35 %. Si l'alimentation reste stable, tu peux
# tester ensuite 0.40 puis 0.50.
PIVOT_SPEED = 0.35

LINE_LOOP_DELAY = 0.02  # environ 50 lectures/s


# ==========================================================
# FILTRAGE CAPTEURS
# ==========================================================

FILTER_WINDOW = 3

left_samples = deque(maxlen=FILTER_WINDOW)
right_samples = deque(maxlen=FILTER_WINDOW)


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
# ÉTAT
# ==========================================================

line_state_lock = threading.Lock()

last_line_action = "initialisation"

last_left_raw: Optional[int] = None
last_right_raw: Optional[int] = None

last_left_filtered: Optional[int] = None
last_right_filtered: Optional[int] = None


def sensor_detects_line(
    value: Optional[int],
) -> Optional[bool]:
    if value is None:
        return None

    return value == LINE_ACTIVE_STATE


def _majority(values) -> int:
    if not values:
        return 0

    ones = sum(values)
    zeros = len(values) - ones

    return 1 if ones >= zeros else 0


def read_line_state() -> dict:
    global last_left_raw, last_right_raw
    global last_left_filtered, last_right_filtered

    left_raw = int(left_sensor.value)
    right_raw = int(right_sensor.value)

    left_samples.append(left_raw)
    right_samples.append(right_raw)

    left_filtered = _majority(left_samples)
    right_filtered = _majority(right_samples)

    with line_state_lock:
        last_left_raw = left_raw
        last_right_raw = right_raw

        last_left_filtered = left_filtered
        last_right_filtered = right_filtered

    return {
        "left_raw": left_raw,
        "right_raw": right_raw,

        "left_filtered": left_filtered,
        "right_filtered": right_filtered,

        "left_detected": sensor_detects_line(
            left_filtered
        ),

        "right_detected": sensor_detects_line(
            right_filtered
        ),
    }


def _drive_straight() -> None:
    drive_control.set_auto_wheel_speeds(
        STRAIGHT_SPEED,
        STRAIGHT_SPEED,
    )


def _pivot_left() -> None:
    """
    Gauche vers arrière, droite vers avant.
    """
    drive_control.set_auto_wheel_speeds(
        -PIVOT_SPEED,
        +PIVOT_SPEED,
    )


def _pivot_right() -> None:
    """
    Gauche vers avant, droite vers arrière.
    """
    drive_control.set_auto_wheel_speeds(
        +PIVOT_SPEED,
        -PIVOT_SPEED,
    )


def line_follower_loop(
    shutdown_event: threading.Event,
) -> None:
    global last_line_action

    print()
    print("Suivi de ligne prêt.")
    print(
        f"FC-51 gauche : GPIO{LEFT_SENSOR_PIN}, "
        f"pin physique {LEFT_SENSOR_PHYSICAL_PIN}"
    )
    print(
        f"FC-51 droit  : GPIO{RIGHT_SENSOR_PIN}, "
        f"pin physique {RIGHT_SENSOR_PHYSICAL_PIN}"
    )
    print(f"État noir configuré : {LINE_ACTIVE_STATE}")
    print(f"Vitesse ligne droite : {STRAIGHT_SPEED:.2f}")
    print(f"Vitesse pivot        : {PIVOT_SPEED:.2f}")
    print(f"Filtre FC-51         : {FILTER_WINDOW} mesures")
    print()

    previous_action: Optional[str] = None

    while not shutdown_event.is_set():

        # Les capteurs restent lus même en mode manuel.
        # Cela permet à /status d'afficher leurs valeurs actuelles.
        sensors = read_line_state()

        if not drive_control.is_autopilot_enabled():
            with line_state_lock:
                last_line_action = "inactif_mode_manuel"

            previous_action = None
            shutdown_event.wait(LINE_LOOP_DELAY)
            continue

        left_detected = sensors["left_detected"]
        right_detected = sensors["right_detected"]

        if left_detected and not right_detected:
            action = "pivot_gauche"
            _pivot_left()

        elif right_detected and not left_detected:
            action = "pivot_droite"
            _pivot_right()

        else:
            # 0/0 : ligne supposée entre les deux capteurs.
            # 1/1 : les deux voient du noir -> continuer droit.
            action = (
                "avancer_deux_sur_noir"
                if left_detected and right_detected
                else "avancer_ligne_au_milieu"
            )

            _drive_straight()

        with line_state_lock:
            last_line_action = action

        if action != previous_action:
            print(
                "FC51 "
                f"raw G={sensors['left_raw']} D={sensors['right_raw']} | "
                f"filtré G={sensors['left_filtered']} "
                f"D={sensors['right_filtered']} | "
                f"action={action}"
            )

            previous_action = action

        shutdown_event.wait(LINE_LOOP_DELAY)

    drive_control.clear_directions(stop=True)

    print("Thread suivi de ligne arrêté.")


def line_follower_state() -> dict:
    with line_state_lock:
        left_raw = last_left_raw
        right_raw = last_right_raw

        left_filtered = last_left_filtered
        right_filtered = last_right_filtered

        action = last_line_action

    return {
        "enabled": drive_control.is_autopilot_enabled(),
        "line_active_state": LINE_ACTIVE_STATE,

        "filter_window": FILTER_WINDOW,
        "straight_speed": STRAIGHT_SPEED,
        "pivot_speed": PIVOT_SPEED,

        "left": {
            "gpio": LEFT_SENSOR_PIN,
            "physical_pin": LEFT_SENSOR_PHYSICAL_PIN,

            "raw": left_raw,
            "filtered": left_filtered,

            "line_detected": sensor_detects_line(
                left_filtered
            ),
        },

        "right": {
            "gpio": RIGHT_SENSOR_PIN,
            "physical_pin": RIGHT_SENSOR_PHYSICAL_PIN,

            "raw": right_raw,
            "filtered": right_filtered,

            "line_detected": sensor_detects_line(
                right_filtered
            ),
        },

        "action": action,
    }


def cleanup() -> None:
    left_sensor.close()
    right_sensor.close()

    print("FC-51 libérés.")
