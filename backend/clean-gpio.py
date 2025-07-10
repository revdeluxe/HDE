import RPi.GPIO as GPIO
from SX127x.board_config import BOARD

GPIO.setmode(GPIO.BCM)
GPIO.cleanup()