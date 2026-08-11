#!/usr/bin/env python3
"""
Contrôle moteur partagé du Smart RC Car.

Ce module est le SEUL propriétaire des GPIO moteurs.

Pilotage manuel :
    rc_unified.py
        -> set_axis()
        -> set_throttle()

Pilotage automatique :
    line_auto.py
        -> set_motion()

Modes :
    MANUAL -> seules les commandes source="manual" sont acceptées
    AUTO   -> seules les commandes source="auto" sont acceptées
"""

from __future__ import annotations

import threading
from typing import Optional

from gpiozero import Motor, PWMOutputDevice


# ==========================================================
# CONFIGURATION GPIO MOTEURS
# ==========================================================

VALID_AXES = {"forward", "backward", "left", "right"}

# Moteur gauche
left_motor = Motor(forward=17, backward=22)
left_pwm = PWMOutputDevice(18)

# Moteur droit
right_motor = Motor(forward=23, backward=24)
right_pwm = PWMOutputDevice(13)


# ==========================================================
# VERROUS
# ==========================================================

# Protège :
# - throttle
# - is_left
# - is_right
# - autopilot_enabled
control_lock = threading.RLock()

# Protège les accès aux moteurs et leur état.
motor_lock = threading.Lock()


# ==========================================================
# ÉTAT
# ==========================================================

throttle = 0.0
is_left = False
is_right = False

current_left_speed = 0.0
current_right_speed = 0.0

autopilot_enabled = False


# ==========================================================
# UTILITAIRES
# ==========================================================

def clamp(
    value: float,
    minimum: float = -1.0,
    maximum: float = 1.0,
) -> float:
    return max(minimum, min(maximum, value))


def drive_side(motor, pwm, speed: float) -> None:
    """
    Applique une vitesse signée sur un moteur.

    speed > 0 : marche avant
    speed < 0 : marche arrière
    speed = 0 : arrêt
    """
    speed = clamp(speed)
    magnitude = abs(speed)

    if magnitude <= 0.0:
        pwm.value = 0
        motor.stop()
        return

    pwm.value = magnitude

    if speed > 0:
        motor.forward()
    else:
        motor.backward()


# ==========================================================
# VITESSES PHYSIQUES
# ==========================================================

def set_motor_speeds(left_speed: float, right_speed: float) -> None:
    global current_left_speed, current_right_speed

    left_speed = clamp(left_speed)
    right_speed = clamp(right_speed)

    with motor_lock:
        # Évite les écritures inutiles lorsque la consigne n'a pas changé.
        if (
            abs(left_speed - current_left_speed) < 0.001
            and abs(right_speed - current_right_speed) < 0.001
        ):
            return

        drive_side(left_motor, left_pwm, left_speed)
        drive_side(right_motor, right_pwm, right_speed)

        current_left_speed = left_speed
        current_right_speed = right_speed


def stop_motors() -> None:
    set_motor_speeds(0.0, 0.0)


def motor_state() -> dict:
    with motor_lock:
        return {
            "left_speed": current_left_speed,
            "right_speed": current_right_speed,
        }


# ==========================================================
# MODE / SOURCE
# ==========================================================

def _source_allowed_locked(source: str) -> bool:
    """
    Vérifie qu'une commande correspond au mode actif.

    MANUAL :
        source="manual" -> accepté
        source="auto"   -> refusé

    AUTO :
        source="auto"   -> accepté
        source="manual" -> refusé
    """
    if source == "auto":
        return autopilot_enabled

    if source == "manual":
        return not autopilot_enabled

    return False


def is_autopilot_enabled() -> bool:
    with control_lock:
        return autopilot_enabled


# ==========================================================
# CALCUL DES VITESSES
# ==========================================================

def _apply_drive_locked() -> None:
    """
    Convertit throttle + gauche/droite en vitesses moteurs.

    control_lock doit déjà être acquis.
    """
    steer = -1.0 if is_left else (1.0 if is_right else 0.0)

    speed_limit = abs(throttle)
    effective_steer = steer * speed_limit

    left_speed = clamp(
        throttle + effective_steer,
        -speed_limit,
        speed_limit,
    )

    right_speed = clamp(
        throttle - effective_steer,
        -speed_limit,
        speed_limit,
    )

    set_motor_speeds(left_speed, right_speed)


# ==========================================================
# COMMANDES MANUELLES / AXES
# ==========================================================

def set_axis(
    axis: str,
    active: bool,
    *,
    source: str = "manual",
    speed: Optional[float] = None,
) -> bool:
    """
    Commande un axe.

    Utilisée principalement par l'API HTTP en mode manuel.

    Retourne False si :
    - l'axe est inconnu ;
    - la source ne correspond pas au mode courant.
    """
    global throttle, is_left, is_right

    if axis not in VALID_AXES:
        return False

    with control_lock:
        if not _source_allowed_locked(source):
            return False

        if axis == "forward":
            if active:
                throttle = clamp(
                    speed if speed is not None else 1.0
                )
            else:
                throttle = 0.0

        elif axis == "backward":
            if active:
                value = speed if speed is not None else 1.0
                throttle = -abs(clamp(value))
            else:
                throttle = 0.0

        elif axis == "left":
            is_left = active
            if active:
                is_right = False

        elif axis == "right":
            is_right = active
            if active:
                is_left = False

        _apply_drive_locked()

    return True


def set_throttle(
    value: float,
    *,
    source: str = "manual",
) -> bool:
    global throttle

    with control_lock:
        if not _source_allowed_locked(source):
            return False

        throttle = clamp(value)
        _apply_drive_locked()

    return True


# ==========================================================
# COMMANDE ATOMIQUE POUR LE MODE AUTO
# ==========================================================

def set_motion(
    speed: float,
    *,
    left: bool = False,
    right: bool = False,
    source: str = "auto",
) -> bool:
    """
    Applique une consigne complète en une seule opération.

    Exemple :
        set_motion(
            0.4,
            right=True,
            source="auto",
        )

    Cela évite plusieurs états moteurs intermédiaires.
    """
    global throttle, is_left, is_right

    if left and right:
        return False

    with control_lock:
        if not _source_allowed_locked(source):
            return False

        throttle = clamp(speed)
        is_left = bool(left)
        is_right = bool(right)

        _apply_drive_locked()

    return True


# ==========================================================
# RESET / STOP
# ==========================================================

def clear_directions(*, stop: bool = True) -> None:
    """
    Remet throttle et directions à zéro.
    Ne modifie pas directement le mode.
    """
    global throttle, is_left, is_right

    with control_lock:
        throttle = 0.0
        is_left = False
        is_right = False

        if stop:
            stop_motors()


def stop_all(disable_autopilot: bool = True) -> None:
    """
    Arrêt complet.

    Peut désactiver l'autopilote, ce qui permet à /control/stop
    de servir d'arrêt global.
    """
    global autopilot_enabled, throttle, is_left, is_right

    with control_lock:
        if disable_autopilot:
            autopilot_enabled = False

        throttle = 0.0
        is_left = False
        is_right = False

        stop_motors()


# ==========================================================
# BASCULE DE MODE
# ==========================================================

def enable_manual_mode() -> None:
    """
    Passage vers le pilotage manuel.

    Supprime toute ancienne consigne automatique et arrête
    la voiture avant de rendre la main à l'API.
    """
    global autopilot_enabled, throttle, is_left, is_right

    with control_lock:
        autopilot_enabled = False

        throttle = 0.0
        is_left = False
        is_right = False

        stop_motors()

    print("Mode MANUEL activé")


def enable_auto_mode() -> None:
    """
    Passage vers le suivi de ligne automatique.

    La voiture est d'abord arrêtée puis l'autopilote est activé.
    """
    global autopilot_enabled, throttle, is_left, is_right

    with control_lock:
        throttle = 0.0
        is_left = False
        is_right = False

        stop_motors()

        autopilot_enabled = True

    print("Mode AUTOMATIQUE activé")


# ==========================================================
# ÉTAT MANUEL
# ==========================================================

def manual_state() -> dict:
    with control_lock:
        return {
            "throttle": throttle,
            "left": is_left,
            "right": is_right,
        }


# ==========================================================
# CLEANUP
# ==========================================================

def cleanup() -> None:
    stop_all(disable_autopilot=True)

    left_pwm.close()
    right_pwm.close()

    left_motor.close()
    right_motor.close()

    print("GPIO moteurs libérés.")
