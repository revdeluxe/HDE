# TX.py

from pyLoRa.lora_module import LoRa
from pyLoRa.configure import run_checks, check_spi, check_gpio

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
    lora = LoRa()
    lora.reset()
    lora.set_frequency(433)
    lora.set_tx_power(14)

    data = b"Hello World"
    print("📤 Sending:", data)
    lora.send(data)

    print("✅ Message sent.")
    lora.close()

if __name__ == "__main__":
    main()
