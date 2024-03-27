import board
import digitalio
import time

motor = digitalio.DigitalInOut(board.A2)
motor.direction = digitalio.Direction.OUTPUT

button = digitalio.DigitalInOut(board.D10)
button.direction = digitalio.Direction.INPUT

speed = 0.05

loop_counter = 0
refresh_rate = 120 # Hz
loop_sleep = 1/refresh_rate # s
current_time = time.time()
time_since_new_emotion = 0

prev_button_val = False
button_count = 0

# Dictionary tracking spinning time for each emotion
emotions = {
    "Neutral" : 0,
    "Jump" : 0.001,
    "Excited" : 1
}
emotion = "Neutral"

while (True):
    current_time = time.time()

    # Tracking pressing
    if prev_button_val == False and button.value == True: # new button press
        button_count += 1
        prev_button_val = True
        if button_count >= 10: # Set excited emotion
            emotion = "Excited"
            time_since_new_emotion = current_time
            button_count = 0
        else:
            emotion = "Jump"
            time_since_new_emotion = current_time
    elif prev_button_val == True and button.value == False: # end of button press
        prev_button_val = False

    if current_time - time_since_new_emotion > emotions.get(emotion):
        motor.value = False
    else:
        motor.value = True

    # Update
    print(f"{loop_counter}: button_count:{button_count} button.value{button.value}")

    loop_counter += 1
    time.sleep(loop_sleep)