# interface.py

import time
from utils import encode_message, decode_message
from SX127x.LoRa import MODE


class LoRaInterface:
    def __init__(self, radio):
        self.radio = radio
        self.rx_mode_active = False
        self.set_mode(MODE.SLEEP)

    def set_mode(self, mode):
        return self.radio.set_mode(mode)

    def switch_to_rx(self):
        self.radio.set_mode(MODE.STDBY)
        self.radio.set_mode(MODE.RXCONT)
        self.rx_mode_active = True

    def switch_to_tx(self, payload_bytes):
        self.radio.write_payload(payload_bytes)
        self.radio.set_mode(MODE.TX)
        time.sleep(0.1)
        self.switch_to_rx()

    def listen_once(self, timeout=3):
        self.switch_to_rx()
        start = time.time()
        while time.time() - start < timeout:
            flags = self.radio.get_irq_flags()
            if flags.get('rx_done'):
                self.radio.clear_irq_flags()
                payload = self.radio.read_payload(nocheck=True)
                return payload, {"rssi": self.radio.get_rssi(), "snr": self.radio.get_snr()}
            time.sleep(0.05)
        return None, {}

    def broadcast(self, payload_bytes, timeout=1):
        self.switch_to_tx(payload_bytes)
        time.sleep(timeout)

    def sync(self):
        self.switch_to_rx()
        
    def get_register(self, addr: int):
        return self.radio.get_register(addr)
    
    def listen_once(self, timeout=3):
        self.switch_to_rx()
        start = time.time()
        while time.time() - start < timeout:
            payload = self.radio.read_payload(nocheck=True)
            if payload:
                self.radio.clear_irq_flags()
                return payload, {
                    "rssi": self.get_rssi(),
                    "snr": self.get_snr(),
                    "loopback": True
                }
            time.sleep(0.05)
        return None, {}
        
    def sync_to_peer(self, message_dict, timeout=3):
        self.switch_to_tx(encode_message(message_dict))
        time.sleep(timeout)
        self.switch_to_rx()
        
    def initiate_handshake(self, my_hostname="node-A", timeout=5):
        payload = encode_message({
            "type": "HANDSHAKE_REQ",
            "from": my_hostname,
            "timestamp": int(time.time())
        })
        self.switch_to_tx(payload)
        time.sleep(0.5)
        self.switch_to_rx()

        start = time.time()
        while time.time() - start < timeout:
            flags = self.radio.get_irq_flags()
            if flags.get("rx_done"):
                self.radio.clear_irq_flags()
                reply = self.radio.read_payload(nocheck=True)
                try:
                    msg = decode_message(reply)
                    if msg.get("type") == "HANDSHAKE_ACK":
                        print(f"?? Handshake confirmed with {msg['from']}")
                        return msg["from"]
                except:
                    pass
            time.sleep(0.1)
        return None  # no handshake received

    def get_rssi(self):
        raw = self.get_register(0x1A)
        return -137 + raw if raw < 256 else None

    def get_snr(self):
        raw = self.get_register(0x1B)
        return raw / 4.0 - 32 if raw < 256 else None

    def get_status(self):
        return {
            "rx_mode_active": self.rx_mode_active,
            "rssi": self.get_rssi(), # fails
            "snr": self.get_snr() # fails
        }

    
