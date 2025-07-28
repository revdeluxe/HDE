import lgpio
import time

CS_PIN = 8
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, 17, 0)  # RESET = 17

# Pulse reset
lgpio.gpio_write(h, 17, 0)
time.sleep(0.1)
lgpio.gpio_write(h, 17, 1)
time.sleep(0.1)

def read_register(addr):
    lgpio.gpio_write(h, CS_PIN, 0)
    result = lgpio.spi_xfer2(h, [addr & 0x7F, 0x00])
    lgpio.gpio_write(h, CS_PIN, 1)
    return result[1]

print("Reg 0x42 =", hex(read_register(0x42)))

lgpio.gpiochip_close(h)

