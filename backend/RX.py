# TX.py

from pyLoRa.lora_module import LoRa
from pyLoRa.configure import run_checks, check_spi, check_gpio
import time

def configure_lora():
    """
    Run preflight checks and configure LoRa module.
    """
    if not run_checks():
        print("[❌] System check failed. Please resolve issues and try again.")
        return False
    print("[✅] LoRa module configured successfully.")
    return True

def main():
    configure_lora()
    lora = LoRa()
    lora.reset()
    lora.set_frequency(433)  # MHz
    lora.set_tx_power(14)    # dBm

    lora.set_mode_rx()
    last_message = None

    while True:
        if not lora.receive():
            print("No message received, retrying...")
            time.sleep(1)
            current_message = "Null"
            continue
        else:
            current_message = lora.read()
        
        if current_message != last_message:
            print("📥 New message received:", current_message)
            last_message = current_message
            break
        # No else print — silence if there's no change
        time.sleep(1)

    lora.close()

if __name__ == "__main__":
    main()
