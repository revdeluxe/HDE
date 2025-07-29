import lgpio
import time

CHIP = 0  # Usually 0 for default Raspberry Pi
h = lgpio.gpiochip_open(CHIP)

# Define your pins
CS = 8
RESET = 17
DIO0 = 4

# Setup pins
lgpio.gpio_claim_output(h, CS, 1)      # CS HIGH by default
lgpio.gpio_claim_output(h, RESET, 1)   # RESET HIGH
lgpio.gpio_claim_alert(h, DIO0, lgpio.RISING_EDGE)

# Example toggle
lgpio.gpio_write(h, RESET, 0)
time.sleep(0.1)
lgpio.gpio_write(h, RESET, 1)
