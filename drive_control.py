"""
Contrôle moteur partagé (GPIO unique).

Ce module est le seul propriétaire des broches moteurs.
Le pilotage manuel (API HTTP) et le suivi de ligne (line_auto)
passent tous les deux par set_axis / set_throttle — aucune duplication GPIO.
"""

from __future__ import annotations

import threading
from typing import Optional

from gpiozero import Motor, PWMOutputDevice

VALID_AXES = {"forward", "backward", "left", "right"}

left_motor = Motor(forward=17, backward=22)
left_pwm = PWMOutputDevice(18)
right_motor = Motor(forward=23, backward=24)
right_pwm = PWMOutputDevice(13)

motor_lock = threading.Lock()
manual_state_lock = threading.Lock()
autopilot_lock = threading.Lock()

throttle = 0.0
is_left = False
is_right = False
current_left_speed = 0.0
current_right_speed = 0.0
autopilot_enabled = False


def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def drive_side(motor, pwm, speed: float) -> None:
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


def set_motor_speeds(left_speed: float, right_speed: float) -> None:
    global current_left_speed, current_right_speed

    left_speed = clamp(left_speed)
    right_speed = clamp(right_speed)
    with motor_lock:
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


def set_autopilot(enabled: bool, stop_when_disabled: bool = True) -> None:
    global autopilot_enabled
    with autopilot_lock:
        autopilot_enabled = enabled
    if not enabled and stop_when_disabled:
        stop_motors()


def is_autopilot_enabled() -> bool:
    with autopilot_lock:
        return autopilot_enabled


def apply_manual_motors() -> None:
    """Traduit throttle + gauche/droite en vitesses moteurs (même logique API)."""
    steer = -1.0 if is_left else (1.0 if is_right else 0.0)
    speed_limit = abs(throttle)
    effective_steer = steer * speed_limit
    left_speed = clamp(throttle + effective_steer, -speed_limit, speed_limit)
    right_speed = clamp(throttle - effective_steer, -speed_limit, speed_limit)
    set_motor_speeds(left_speed, right_speed)


def set_axis(
    axis: str,
    active: bool,
    *,
    source: str = "manual",
    speed: Optional[float] = None,
) -> bool:
    """
    Fonction unique de réception des directions.

    - source="manual" : appel API mobile → désactive l'autopilote
    - source="auto"   : appel depuis la boucle suivi de ligne → garde l'autopilote
    - speed           : throttle à appliquer pour forward/backward (ex. 0.37 en auto)
    """
    global throttle, is_left, is_right

    if axis not in VALID_AXES:
        return False

    if source != "auto":
        set_autopilot(False, stop_when_disabled=False)

    with manual_state_lock:
        if axis == "forward":
            if active:
                throttle = clamp(speed if speed is not None else 1.0)
            else:
                throttle = 0.0
        elif axis == "backward":
            if active:
                throttle = -clamp(speed if speed is not None else 1.0)
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
        apply_manual_motors()

    return True


def set_throttle(value: float, *, source: str = "manual") -> bool:
    global throttle

    if source != "auto":
        set_autopilot(False, stop_when_disabled=False)

    with manual_state_lock:
        throttle = clamp(value)
        apply_manual_motors()
    return True


def clear_directions(*, stop: bool = True) -> None:
    """Remet throttle / virages à zéro (sans forcément toucher au flag autopilote)."""
    global throttle, is_left, is_right
    with manual_state_lock:
        throttle = 0.0
        is_left = False
        is_right = False
    if stop:
        stop_motors()


def stop_all(disable_autopilot: bool = True) -> None:
    if disable_autopilot:
        set_autopilot(False, stop_when_disabled=False)
    clear_directions(stop=True)


def manual_state() -> dict:
    with manual_state_lock:
        return {"throttle": throttle, "left": is_left, "right": is_right}


def enable_manual_mode() -> None:
    """Bascule in-process vers le pilotage manuel (pas de redémarrage)."""
    set_autopilot(False, stop_when_disabled=True)
    clear_directions(stop=True)


def enable_auto_mode() -> None:
    """Bascule in-process vers le suivi de ligne (pas de redémarrage)."""
    clear_directions(stop=True)
    set_autopilot(True, stop_when_disabled=False)


def cleanup() -> None:
    stop_all(disable_autopilot=True)
    left_pwm.close()
    right_pwm.close()
    left_motor.close()
    right_motor.close()
