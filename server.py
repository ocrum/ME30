from flask import Flask
import RPi.GPIO as GPIO
import requests  # For sending HTTP requests weeee!!!
import threading

import serial
import time

app = Flask(__name__)

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
motor_pin = 12
GPIO.setup(motor_pin, GPIO.OUT)
pwm = GPIO.PWM(motor_pin, 500)
pwm.start(0)


class RobotManager():
    def __init__(self, refresh_rate=10, motor_pin=12):
        # Serial setup
        self.ser = None
        self.ser_port = '/dev/ttyS0'
        self.open_serial_port()

        # Loop variables
        self.is_running = False
        self.waiting_freq = 3  # Hz
        self.running_freq = 1  # Hz
        self.loop_length = 1 / self.waiting_freq

        # Pot variables
        self.max_pot_val = 26000
        self.min_pot_val = 17000
        self.pot_dead_zone = 2000  # TODO CHANGE

        # Motor variables
        self.max_motor_pwm = 100  # TODO CHANGE
        self.min_motor_pwm = 70  # TODO CHANGE
        self.motor_corr_factor = 5  # TODO TEST
        self.move_forward_anyways = self.motor_corr_factor/10  # Kind of want to bias to moving forward LOLL!!
        self.motor_speed = 0

        # Motor pin setup


        # Variables for starting
        self.is_ready = False
        self.is_driving = False
        self.personal_delay = 0.5
        self.bestie_robot_ip = "10.243.87.84"
        self.start_tries = 0
        self.max_start_tried = 10


        # JK: "10.243.87.84"
        # B: 10.243.94.63

        # Variables for speed management
        self.max_speed = 500 # mm/second

        self.side = 0  # 0 -> not determined, -1 -> left, 1 -> right

    def open_serial_port(self, baudrate=9600):
        """
        Opens the serial port yay!!
        :param baudrate:
        :return:
        """
        try:
            self.ser = serial.Serial(self.ser_port, baudrate=baudrate, timeout=1)
            print("Serial port opened")
        except serial.SerialException as e:
            print(f"Error opening serial: {e}")

    def read_serial(self):
        """
        Reads from the serial port once
        :return:
        """
        try:
            data = self.ser.read(2)
            if data:
                data = int.from_bytes(data, 'little')
                # print(f"Serial value: {data}")
                if data > self.max_pot_val:
                    data = self.max_pot_val
                elif data < self.min_pot_val:
                    data = self.min_pot_val
                return self.max_pot_val
        except serial.SerialException as e:
            print(f"Serial exception: {e}")
            self.ser.close()
            self.open_serial_port()

    def begin(self, side=0):
        """
        Starts the event loop
        :param side: what side the robot is on
        :return:
        """
        print("Begining the code")
        self.side = side
        self.is_running = True

        self.event_loop()
        # event_loop_thread = threading.Thread(target=self.event_loop)
        # event_loop_thread.start()

    def event_loop(self):
        while self.is_running:
            self.update()
            self.display()

            time.sleep(self.loop_length)

    def display(self):
        """
        For debugging purposes but honestly not the most useful :(
        :return:
        """
        # print(f"Motor speed: {self.motor_speed}")

    def update(self):
        """
        Reads in values and makes logic decisions
        :return:
        """
        if not self.is_driving and not self.is_ready:
            self.loop_length = 1 / self.waiting_freq
            self.send_start_request()
        elif self.is_ready and not self.is_driving:
            time.sleep(self.personal_delay)
            self.is_driving = True
            self.loop_length = 1 / self.running_freq
        elif self.is_driving:
            self.update_motor_speed()

    def start(self, delay):
        self.start_tries += 1

        try:
            delay = float(delay)
        except ValueError as e:
            print(f"Cannot conver {delay} to a number {e}")
            return "no"

        if self.is_driving or not (0 <= delay <= 15):
            return "no"

        delay = float(delay)
        print(f"Accepted delay {delay}")
        self.personal_delay = delay
        self.is_ready = True

        return "ok"

    def send_start_request(self):
        """
        Ask your bff when they want to start
        :return:
        """
        self.max_start_tried += 1

        # Give up and just go
        if self.start_tries >= self.max_start_tried:
            self.is_ready = True

        url = f'http://{self.bestie_robot_ip}/start/{self.personal_delay}'
        response = "no"
        try:
            print(f"Sending request to {url}")
            response = requests.get(url)
            response = response.text
        except requests.exceptions.RequestException as e:
            print(f"Error talking to bestie bff robot at {self.bestie_robot_ip}. I hope their robot works!! {e}")

        if response == "ok":
            self.is_ready = True

    def target(self, speed):
        try:
            delay = float(speed)
        except ValueError as e:
            print(f"Cannot conver {delay} to a number {e}")
            return "no"

        if not (0 <= speed <= self.max_speed):
            return "no"
        else:
            return "ok"

    def send_target_request(self, speed):
        url = f'http://{self.bestie_robot_ip}/temp/{speed}'
        try:
            response = requests.get(url)
            return response.text
        except requests.exceptions.RequestException as e:
            return f"Error talking to bestie bff robot at {self.bestie_robot_ip}. I hope their robot works!! {e}"

    def update_motor_speed(self):
        """
        Update the motor speed from the pot value
        :return:
        """
        global pwm

        # normalized_pot_val = self.pot_to_speed_change()

        # change = self.motor_corr_factor * normalized_pot_val + self.move_forward_anyways

        # if change + self.motor_speed > self.max_motor_pwm:
        #     self.motor_speed = self.max_motor_pwm
        # if change + self.motor_speed < self.min_motor_pwm:
        #     self.motor_speed = self.min_motor_pwm

        self.motor_speed = self.min_motor_pwm

        # print(f"Nromalized pot value: {normalized_pot_val} Change: {change} Motor sped: {self.motor_speed}")
        pwm.ChangeDutyCycle(self.motor_speed)

    def pot_to_speed_change(self):
        """
        Convert the raw potentiometer value into how much to correct the tube (-1 to 1)
        :return: The correction magnitude normalized (-1 to 1)
        """
        pot_value = self.read_serial()
        print(f"Pot value!: {pot_value}")
        mid_value = (self.max_pot_val + self.min_pot_val) / 2

        if abs(pot_value - mid_value) <= self.pot_dead_zone:
            return 0

        if pot_value > mid_value:  # Tube tilting right
            # If on right side (positive side) and tilting right, robot should speed up
            return self.side * (pot_value - mid_value) / (self.max_pot_val - mid_value)
        else:  # Tube tilting left
            return self.side * (pot_value - mid_value) / (mid_value - self.min_pot_val)

    def stop(self):
        """
        Stops the event loop
        :return:
        """
        self.is_running = False
        self.ser.close()


manager = RobotManager()  # Probably want to keep this line here because the call below use this object



@app.route('/load/<side>')
def load(side):
    """
    The function that starts our robot!!
    :param side:
    :return:
    """

    if side == 'left':
        manager.begin(-1)
    elif side == 'right':
        manager.begin(1)
    else:
        return "Invalid side"

    print(f"Loaded on side {side}")
    return f"Loaded on side {side}"

# It would be nice to just have flask call the methods in the class (and I think there is a way to but it seems scary
# and I don't want to change too many things so here we are)
@app.route('/start/<delay>')
def start(delay):
    return manager.start(delay)

@app.route('/target/<speed>')
def target(speed):
    return manager.target(speed)

@app.route('/')
def hello_world():
    return 'Hello, World!'

# =============================BASIC SECTION OF CODE TO TURN PIN ON OR OFF ===================================================
# Below we take input from a web browser and channel it to GPIO pin.
# app.route refers to your Pi's IP address, which you'll type into a web browser URL line when you want to control this code.
# For example, to set pin 16 on your Pi to HIGH, in your web browser you'll type [your Pi IP address]/digital/write/16/HIGH.
# Make sure the line below has the correct angle brackets in it.
@app.route('/digital/write/<pin_name>/<state>')
def digital_write(pin_name, state):
    pin = int(pin_name)
    if state.upper() in ['1', 'ON', 'HIGH']:
        GPIO.setup(pin, GPIO.OUT)  # make the pin an output
        GPIO.output(pin, GPIO.HIGH)  # turn the pin on
        return 'Set pin {0} to HIGH!!!!!'.format(pin_name)
    elif state.upper() in ['0', 'OFF', 'LOW']:
        GPIO.setup(pin, GPIO.OUT)  # make the pin an output
        GPIO.output(pin, GPIO.LOW)  # turn the pin off
        return 'Set pin {0} to LOW!!!!!'.format(pin_name)
    return 'Something went wrong'


# ========================================================== Hardcoding PWM ===#
@app.route('/pwmtest/<duty>')
def pwmtest(duty):

    global pwm
    duty = int(duty)
    pwm.ChangeDutyCycle(duty)
    return f'running PWM at {duty}'

# # Set up serial communication
# ser = serial.Serial('/dev/ttyS0', baudrate=9600, timeout=1)

# try:
#     while True:
#         # Read potentiometer value (assuming a 16-bit value)
#         pot_bytes = ser.read(2)

#         # Convert bytes to integer
#         pot_value = int.from_bytes(pot_bytes, 'little')

#         # Process potentiometer value as needed
#         print("Potentiometer Value:", pot_value)

# except KeyboardInterrupt:
#     # Close the serial port on Ctrl+C
#     ser.close()
