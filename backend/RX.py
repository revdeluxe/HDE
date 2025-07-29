from lora_module import LoRa
from lora_handler import LoRaGPIOHandler
from configure import check_spi, check_gpio
import time

def run_checks() -> bool:
    print("🔍 Running preflight system check...\n")
    spi_ok = check_spi()
    gpio_ok = check_gpio()

    if spi_ok and gpio_ok:
        print("\n✅ System ready. All LoRa dependencies satisfied.")
        return True
    else:
        print("\n❌ System check failed. Please resolve issues and try again.")
        return False

def main():
    if not run_checks():
        return

    lora = LoRa()
    lora.reset()
    lora.set_frequency(433)

    print("📡 Listening for LoRa messages... (Press Ctrl+C to stop)")
    try:
        while True:
            if lora.received():
                payload = lora.read()
                if payload:
                    print("📥 Received:", payload.decode('utf-8', errors='ignore'))
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 Receiver stopped by user.")
    finally:
        lora.close()

if __name__ == "__main__":
    main()
