# TX.py

from pyLoRa.lora_module import LoRa
from pyLoRa.configure import run_checks, check_spi, check_gpio
import time

def configure_lora():
    """
    Run preflight checks and configure LoRa module.
    """
    run_checks()
    return True

def main():
    configure_lora()
    lora = LoRa()
    lora.reset()
    lora.set_frequency(433)
    lora.set_tx_power(14)
    lora.set_mode_rx()

    last_packet = None

    while True:
        if lora.receive():
            packet = lora.read()
            if packet != last_packet:
                print("📥 New packet received:", packet)
                last_packet = packet
                b
        # Optionally add a sleep to avoid CPU overload
        # time.sleep(0.5)
        time.sleep(0.1)

    lora.close()

if __name__ == "__main__":
    main()
