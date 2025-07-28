import lgpio
import time

h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, 17, 0)  # RESET = 17

# Pulse reset
lgpio.gpio_write(h, 17, 0)
time.sleep(0.1)
lgpio.gpio_write(h, 17, 1)
time.sleep(0.1)

lgpio.gpiochip_close(h)
