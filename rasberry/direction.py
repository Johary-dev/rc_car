et voici un autre

import curses
from gpiozero import Motor, PWMOutputDevice


class Vehicle:
    def __init__(self):
        # Moteur gauche
        self.left_motor = Motor(forward=17, backward=22)
        self.left_pwm = PWMOutputDevice(18)
        self.left_pwm.value = 0

        # Moteur droit
        self.right_motor = Motor(forward=23, backward=24)
        self.right_pwm = PWMOutputDevice(13)
        self.right_pwm.value = 0

    def forward(self):
        self.left_pwm.value = 1
        self.right_pwm.value = 1

        self.left_motor.forward()
        self.right_motor.forward()

    def backward(self):
        self.left_pwm.value = 1
        self.right_pwm.value = 1

        self.left_motor.backward()
        self.right_motor.backward()

    def left(self):
        self.left_pwm.value = 1
        self.right_pwm.value = 1

        self.left_motor.backward()
        self.right_motor.forward()

    def right(self):
        self.left_pwm.value = 1
        self.right_pwm.value = 1

        self.left_motor.forward()
        self.right_motor.backward()

    def stop(self):
        self.left_motor.stop()
        self.right_motor.stop()

        self.left_pwm.value = 0
        self.right_pwm.value = 0

    def map_key_to_command(self, key):
        commands = {
            curses.KEY_UP: self.forward,
            curses.KEY_DOWN: self.backward,
            curses.KEY_LEFT: self.left,
            curses.KEY_RIGHT: self.right
        }
        return commands.get(key)

    def control(self, key):
        return self.map_key_to_command(key)


rpi_vehicle = Vehicle()


def main(window):
    next_key = None

    while True:
        curses.halfdelay(1)

        if next_key is None:
            key = window.getch()
            print(key)
        else:
            key = next_key
            next_key = None

        if key != -1:
            action = rpi_vehicle.control(key)

            if action:
                action()

            next_key = key

            while next_key == key:
                next_key = window.getch()

            rpi_vehicle.stop()


curses.wrapper(main)