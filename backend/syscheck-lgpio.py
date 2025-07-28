import lgpio
import spidev
import time

RESET_PIN = 17  # GPIO 17 (Pin 11)

# ---- Reset LoRa module via GPIO 17 ----
chip = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(chip, RESET_PIN, 0)
lgpio.gpio_write(chip, RESET_PIN, 0)
time.sleep(0.1)
lgpio.gpio_write(chip, RESET_PIN, 1)
time.sleep(0.1)
lgpio.gpiochip_close(chip)

# ---- SPI Communication ----
def read_register(reg_addr):
    spi = spidev.SpiDev()
    spi.open(0, 0)  # spidev0.0
    spi.max_speed_hz = 500000
    response = spi.xfer2([reg_addr & 0x7F, 0x00])
    spi.close()
    return response[1]

# ---- Test Register 0x42 ----
reg_val = read_register(0x42)
print("Reg 0x42 =", hex(reg_val))
