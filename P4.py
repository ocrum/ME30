import board
import pwmio
import time

from adafruit_motor import stepper
from analogio import AnalogIn
from digitalio import DigitalInOut, Direction

# Initialize pins
motor_IN2 = DigitalInOut(board.D4)
motor_IN1 = DigitalInOut(board.D3)
motor_ENA = pwmio.PWMOut(board.D2, frequency=5000, duty_cycle=0)

stepper_IN4 = DigitalInOut(board.D5)
stepper_IN3 = DigitalInOut(board.D6)
stepper_IN2 = DigitalInOut(board.D7)
stepper_IN1 = DigitalInOut(board.D8)

joystick_VRX = AnalogIn(board.A1)
joystick_VRY = AnalogIn(board.A0)
joystick_SW = DigitalInOut(board.D0)
button = DigitalInOut(board.D10)

# Set input vs output
motor_IN2.direction = Direction.OUTPUT
motor_IN1.direction = Direction.OUTPUT

stepper_IN4.direction = Direction.OUTPUT
stepper_IN3.direction = Direction.OUTPUT
stepper_IN2.direction = Direction.OUTPUT
stepper_IN1.direction = Direction.OUTPUT

joystick_SW.direction = Direction.INPUT
button.direction = Direction.INPUT

XY_motor = stepper.StepperMotor(stepper_IN1, stepper_IN2, stepper_IN3, stepper_IN4, microsteps=None)

# Game states
GAME_OVER = 0
NEW_GAME = 1
RUNNING = 2

# Max analogue value
MAX_VAL = 65535

# Variables for debouncing
prev_joystick_SW = joystick_SW.value
prev_button = button.value


def process_inputs():
    """
    Processes the state of the game and controls the speed and status
    :return: none
    """

    global curr_state, speed, stepper_speed, start_time, prev_joystick_SW, prev_button, score

    # debouncing tracking
    if joystick_SW.value is False and prev_joystick_SW is True:
        prev_joystick_SW = False
    if button.value is False and prev_button is True:
        prev_button = False

    # GAME OVER: nothing can move only can see score of the game
    if curr_state == GAME_OVER:
        speed = 0
        stepper_speed = 0
        if joystick_SW.value is True and prev_joystick_SW is False:
            curr_state = NEW_GAME
        return

    # NEW GAME: can move everything to set up everything
    if curr_state == NEW_GAME:
        speed = joystick_to_speed(joystick_VRX.value)
        stepper_speed = joystick_to_speed(joystick_VRY.value)
        if joystick_SW.value is True and prev_joystick_SW is False:
            start_time = time.monotonic_ns()
            curr_state = RUNNING
        return

    # RUNNING: playing the game
    if curr_state == RUNNING:
        if button.value is True and prev_button is False:
            curr_state = GAME_OVER
            return
        score = int((prev_time - start_time) / 1e+9)
        speed = 10
        stepper_speed = joystick_to_speed(joystick_VRY.value)


def score_to_speed(score):
    """
    Converts the score of the game into the speed of the motor
    :param score: score of the game
    :return: Speed from 0 to 100
    """

    base_speed = 10
    max_speed = 100

    start_increase_score = 10
    max_speed_score = 60

    if score < start_increase_score:
        return base_speed
    elif score >= max_speed_score:
        return max_speed
    else:
        # Linear mapping
        score_range = max_speed_score - start_increase_score
        speed_range = max_speed - base_speed
        return base_speed + speed_range * (score - start_increase_score) / score_range


def joystick_to_speed(joystick):
    """
    Converts the joystick values into the speed of the motor
    :param joystick: Joystick value directly form pin
    :return: Speed from -100 to 100
    """

    midpoint = MAX_VAL / 2
    dead_zone = 1000  # Range of values to result in a speed of 0
    lower_bound, upper_bound = midpoint - dead_zone, midpoint + dead_zone

    if lower_bound <= joystick <= upper_bound:
        return 0
    elif joystick > upper_bound:
        # Quadratic mapping
        return 100 * ((joystick - upper_bound) / (MAX_VAL - upper_bound)) ** 2
    else:
        # Quadratic mapping
        return 100 * ((joystick - lower_bound) / lower_bound) ** 2


def move_motor(speed):
    """
    Controls the DC motor with PWM
    :param speed: Speed from -100 to 100
    :return: None
    """
    # Limiting the backwards speed
    if speed < -40:
        return

    min_speed = 41200  # Min PWM value to result in visible rotation
    max_speed = MAX_VAL

    # Control direction of the motor
    if speed >= 0:
        motor_IN1.value = False
        motor_IN2.value = True
    else:
        motor_IN1.value = True
        motor_IN2.value = False

    if speed == 0:
        motor_ENA.duty_cycle = 0
    else:
        motor_ENA.duty_cycle = int(min_speed + (max_speed - min_speed) * abs(speed) / 100)


def step_stepper():
    """
    Steps the stepper motor
    :return: None
    """
    global stepper_speed, last_time_stepped
    if stepper_speed > 0:
        XY_motor.onestep(direction=stepper.BACKWARD)
    elif stepper_speed < 0:
        XY_motor.onestep(direction=stepper.FORWARD)
    last_time_stepped = time.monotonic_ns()


def move_stepper():
    """
    Controls the stepper motor to mapping speed to a frequency to step the stepper motor
    :return: None
    """
    global stepper_speed, refresh_rate, last_time_stepped

    if stepper_speed is 0:
        return

    max_speed = 520  # Hz (Calculated from https://www.daycounter.com/Calculators/Stepper-Motor-Calculator.phtml)
    steps_per_sec = max_speed * abs(stepper_speed) / 100
    steps_per_loop = steps_per_sec / refresh_rate
    step_sleep = 1 / steps_per_sec

    # If less than one step per game loop then track last time since step
    if steps_per_loop < 1:
        if (time.monotonic_ns() - last_time_stepped) / 1e+9 > step_sleep:
            step_stepper()
        return

    # If multiple steps in a game loop
    for _ in range(int(steps_per_loop)):
        step_stepper()
        time.sleep(step_sleep)


def display(debug=False):
    """
    Displays the status of the game
    :param debug: If you want to see more information for debugging
    :return: None
    """
    global prev_time, start_time, curr_state, loop_counter, stepper_speed, speed, score

    # What to display for each status of the game
    displays = {
        GAME_OVER: f"GAME OVER! Final score:{score} (Click to play again)",
        NEW_GAME: f"Ready to play? (Move the carriage to set up the game! And Click )",
        RUNNING: f"Score {score}"
    }

    if debug:
        print(f"{loop_counter} X:{joystick_VRX.value} Y:{joystick_VRY.value} " +
              f"Click:{joystick_SW.value} Button:{button.value} STATE:{curr_state} " +
              f"SPEED:{speed} STEPPER DIR:{stepper_speed} ", end="")
    else:
        print("\n\n\n", end="")

    print(f"{displays.get(curr_state)}")


def move():
    move_motor(speed)
    move_stepper()


loop_counter = 0
refresh_rate = 10  # Hz
loop_sleep = 1 / refresh_rate  # s
prev_time = time.monotonic_ns()
start_time = prev_time
last_time_stepped = prev_time
score = 0

curr_state = NEW_GAME
speed = 0
stepper_speed = 0

while True:
    process_inputs()
    move()
    display(debug=False)

    loop_counter += 1

    # Ensuring that the game loop is a certain frequency
    # accounting for time it takes to do tasks within the loop
    curr_time = time.monotonic_ns()
    if curr_time - prev_time < loop_sleep * 1e+9:
        time.sleep(loop_sleep - (curr_time - prev_time) / 1e+9)
    prev_time = time.monotonic_ns()
