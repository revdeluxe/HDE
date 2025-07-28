import spidev
import RPi.GPIO as GPIO
import time

CS_PIN = 8  # or 7 depending on your setup

GPIO.setmode(GPIO.BCM)
GPIO.setup(CS_PIN, GPIO.OUT)
GPIO.output(CS_PIN, GPIO.HIGH)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 500000

def read_register(addr):
    GPIO.output(CS_PIN, GPIO.LOW)
    result = spi.xfer2([addr & 0x7F, 0x00])
    GPIO.output(CS_PIN, GPIO.HIGH)
    return result[1]

print("Reg 0x42 =", hex(read_register(0x42)))

spi.close()
GPIO.cleanup()
