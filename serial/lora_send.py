import serial
import time
import sys

# Accept message from command line argument
if len(sys.argv) < 2:
    print("No message provided.")
    sys.exit(1)

message = sys.argv[1]
serial_port = "/dev/serial0"  # For Windows, e.g., "COM3"
baudrate = 9600

try:
    ser = serial.Serial(serial_port, baudrate, timeout=2)
    ser.write(message.encode())
    ser.close()
    print("Message sent.")
except serial.SerialException as e:
    print(f"Serial error: {e}")
    sys.exit(1)