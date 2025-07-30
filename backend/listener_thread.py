import threading
import json
import time
import os
from parser import parse_message
from pyLoRa import LoRa  # Your custom driver
from datetime import datetime

FILENAME = "messages/messages.json"
lock = threading.Lock()

def ensure_file():
    os.makedirs("messages", exist_ok=True)
    if not os.path.exists(FILENAME):
        with open(FILENAME, 'w') as f:
            f.write("")

def listen_lora_forever():
    ensure_file()
    lora = LoRa()  # Initialize LoRa module
    lora.set_mode_rx()  # Set to receive mode

    print("[LoRa Listener] Started listening...")

    while True:
        if lora.received_packet():
            raw = lora.read_payload()
            parsed = parse_message(raw)
            if parsed:
                with lock:
                    with open(FILENAME, 'a') as f:
                        f.write(json.dumps(parsed) + "\n")
                print(f"[LoRa Listener] Message received: {parsed}")
        time.sleep(0.5)  # Avoid CPU hogging

def get_lora_state():
    """
    Returns the current LoRa state.
    """ 
    return {
        "mode": lora.get_mode(),
        "frequency": lora.get_frequency(),
        "tx_power": lora.get_tx_power(),
        "rssi": lora.get_rssi(),
        "snr": lora.get_snr()
    }