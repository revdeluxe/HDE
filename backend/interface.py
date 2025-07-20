# interface.py

import time
from SX127x.LoRa import MODE

class LoRaInterface:
    def __init__(self, radio):
        self.radio = radio
        self.rx_mode_active = False

        # now safe to set mode here:
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
        time.sleep(0.1)  # Let TX finish
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
        # optional: send “SYNC” handshake here
        
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

    def get_rssi(self):
        # RegPktRssiValue = 0x1A
        raw = self.get_register(0x1A)
        return -137 + raw if raw < 256 else None

    def get_snr(self):
        # RegPktSnrValue = 0x1B
        raw = self.get_register(0x1B)
        return raw / 4.0 - 32 if raw < 256 else None

    def get_status(self):
        return {
            "rx_mode_active": self.rx_mode_active,
            "rssi": self.get_rssi(), # fails
            "snr": self.get_snr() # fails
        }
    
    
