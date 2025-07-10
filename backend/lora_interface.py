# lora_interface.py
import time
from SX127x.LoRa import LoRa
from utils import encode_envelope, decode_envelope

class LoRaSender:
    def __init__(self, radio: LoRa):
        self.radio = radio

    def send_lora(self, env):
            raw = encode_envelope(env)
            print("Sending:", env)
            try:
                result = self.radio.write_payload(list(raw))
                print("Sent bytes:", result)
            except Exception as e:
                print("LoRa send failed:", e)



class LoRaReceiver:
    def __init__(self, radio: LoRa):
        self.radio = radio

    def listen_once(self, timeout=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if hasattr(self.radio, 'rx_done') and self.radio.rx_done():
                try:
                    raw = self.radio.read_payload()
                    self.radio.clear_irq_flags()
                    env = decode_envelope(raw)
                    return env, None
                except Exception:
                    return None, None
            time.sleep(1)
        return None, None

    def get_status(self):
        return {
            "rssi":     self.radio.get_rssi(),
            "snr":      self.radio.get_snr(),
            "gain_dbi": self.radio.get_pa_config().get("output_power", 0)
        }
