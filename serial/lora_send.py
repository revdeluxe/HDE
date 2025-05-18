import serial
import time
import sys

def main():
    # Change this to the correct serial port for your system
    serial_port = "/dev/serial0"  # For Windows, e.g., "COM3"
    baudrate = 9600

    try:
        ser = serial.Serial(serial_port, baudrate, timeout=2)
    except serial.SerialException as e:
        print(f"Could not open serial port: {e}")
        sys.exit(1)

    print("Type messages to send. Press Ctrl+C to exit.")
    try:
        while True:
            data = input("Send: ")
            if not data:
                continue
            ser.write(data.encode())
            print("Sent.")
    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()