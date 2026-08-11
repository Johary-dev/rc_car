#!/usr/bin/env python3
"""
Contrôle moteur partagé du Smart RC Car.

Ce module est le SEUL propriétaire des GPIO moteurs.

- Mode MANUAL : commandes de l'application mobile.
- Mode AUTO   : commandes du suivi de ligne.
- Les virages automatiques peuvent commander directement les vitesses
  signées gauche/droite, ce qui permet les pivots sur place.

Convention :
    +1.0 = marche avant maximale
     0.0 = arrêt
    -1.0 = marche arrière maximale
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from gpiozero import Motor, PWMOutputDevice


VALID_AXES = {"forward", "backward", "left", "right"}

left_motor = Motor(forward=17, backward=22)
left_pwm = PWMOutputDevice(18)

right_motor = Motor(forward=23, backward=24)
right_pwm = PWMOutputDevice(13)

# Coupe brièvement les moteurs avant une inversion franche de sens.
REVERSAL_PAUSE = 0.02

control_lock = threading.RLock()
motor_lock = threading.Lock()

throttle = 0.0
is_left = False
is_right = False

current_left_speed = 0.0
current_right_speed = 0.0

autopilot_enabled = False


def clamp(
    value: float,
    minimum: float = -1.0,
    maximum: float = 1.0,
) -> float:
    return max(minimum, min(maximum, value))


def drive_side(motor, pwm, speed: float) -> None:
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


def _is_direction_reversal(old_speed: float, new_speed: float) -> bool:
    return (
        old_speed != 0.0
        and new_speed != 0.0
        and ((old_speed > 0) != (new_speed > 0))
    )


def set_motor_speeds(left_speed: float, right_speed: float) -> None:
    global current_left_speed, current_right_speed

    left_speed = clamp(left_speed)
    right_speed = clamp(right_speed)

    with motor_lock:
        if (
            abs(left_speed - current_left_speed) < 0.001
            and abs(right_speed - current_right_speed) < 0.001
        ):
            return

        reversing = (
            _is_direction_reversal(current_left_speed, left_speed)
            or _is_direction_reversal(current_right_speed, right_speed)
        )

        if reversing:
            drive_side(left_motor, left_pwm, 0.0)
            drive_side(right_motor, right_pwm, 0.0)

            current_left_speed = 0.0
            current_right_speed = 0.0

            time.sleep(REVERSAL_PAUSE)

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


def _source_allowed_locked(source: str) -> bool:
    if source == "auto":
        return autopilot_enabled

    if source == "manual":
        return not autopilot_enabled

    return False


def is_autopilot_enabled() -> bool:
    with control_lock:
        return autopilot_enabled


def _apply_manual_drive_locked() -> None:
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


def set_axis(
    axis: str,
    active: bool,
    *,
    source: str = "manual",
    speed: Optional[float] = None,
) -> bool:
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

        _apply_manual_drive_locked()

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
        _apply_manual_drive_locked()

    return True


def set_auto_wheel_speeds(
    left_speed: float,
    right_speed: float,
) -> bool:
    """
    Commande atomique réservée au mode automatique.

    Avancer :
        left=+0.37
        right=+0.37

    Pivot gauche :
        left=-0.35
        right=+0.35

    Pivot droite :
        left=+0.35
        right=-0.35
    """
    with control_lock:
        if not autopilot_enabled:
            return False

        set_motor_speeds(
            clamp(left_speed),
            clamp(right_speed),
        )

    return True


# Conservée pour compatibilité éventuelle.
def set_motion(
    speed: float,
    *,
    left: bool = False,
    right: bool = False,
    source: str = "auto",
) -> bool:
    global throttle, is_left, is_right

    if left and right:
        return False

    with control_lock:
        if not _source_allowed_locked(source):
            return False

        throttle = clamp(speed)
        is_left = bool(left)
        is_right = bool(right)

        _apply_manual_drive_locked()

    return True


def clear_directions(*, stop: bool = True) -> None:
    global throttle, is_left, is_right

    with control_lock:
        throttle = 0.0
        is_left = False
        is_right = False

        if stop:
            stop_motors()


def stop_all(disable_autopilot: bool = True) -> None:
    global autopilot_enabled, throttle, is_left, is_right

    with control_lock:
        if disable_autopilot:
            autopilot_enabled = False

        throttle = 0.0
        is_left = False
        is_right = False

        stop_motors()


def enable_manual_mode() -> None:
    global autopilot_enabled, throttle, is_left, is_right

    with control_lock:
        autopilot_enabled = False

        throttle = 0.0
        is_left = False
        is_right = False

        stop_motors()

    print("Mode MANUEL activé")


def enable_auto_mode() -> None:
    global autopilot_enabled, throttle, is_left, is_right

    with control_lock:
        throttle = 0.0
        is_left = False
        is_right = False

        stop_motors()
        autopilot_enabled = True

    print("Mode AUTOMATIQUE activé")


def manual_state() -> dict:
    with control_lock:
        return {
            "throttle": throttle,
            "left": is_left,
            "right": is_right,
        }


def cleanup() -> None:
    stop_all(disable_autopilot=True)

    left_pwm.close()
    right_pwm.close()

    left_motor.close()
    right_motor.close()

    print("GPIO moteurs libérés.")
