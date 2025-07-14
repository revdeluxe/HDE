# LoRa_test.py

import time
import queue
import threading

class DummyRadio:
    MODE_STDBY = "STDBY"
    MODE_TX    = "TX"
    MODE_RX    = "RX"

    def __init__(self):
        self.rx_queue = queue.Queue()
        self.mode     = self.MODE_STDBY
        self._busy_until = 0.0

    def set_mode(self, m):
        now = time.time()
        # enforce that if we're still 'busy' from TX, we can't instantly switch to RX
        if self.mode == self.MODE_TX and now < self._busy_until and m == self.MODE_RX:
            # ignore or delay the switch
            time.sleep(self._busy_until - now)
        self.mode = m

    def write_payload(self, lst):
        # only accept payload if we're in STDBY or TX
        if self.mode not in (self.MODE_STDBY, self.MODE_TX):
            raise RuntimeError(f"Can't write_payload in mode {self.mode}")
        # simulate real air-time
        airtime = 0.01 + len(lst)*0.0001
        self._busy_until = time.time() + airtime
        # enqueue for loopback only after airtime
        threading.Timer(airtime, lambda: self.rx_queue.put(bytes(lst))).start()

    def read_payload(self, nocheck=True):
        return self.rx_queue.get_nowait()

    def get_irq_flags(self):
        return {"rx_done": not self.rx_queue.empty()}

class DummyLoRaInterface:
    def __init__(self, radio=None):
        self.radio = radio or DummyRadio()
        self.lock = threading.Lock()
        self.rx_mode_active = False

    def is_busy(self):
        return time.time() < self.radio._busy_until

    def switch_to_rx(self):
        with self.lock:
            # if still busy, wait out the airtime
            if self.is_busy():
                time.sleep(self.radio._busy_until - time.time())
            self.radio.set_mode(DummyRadio.MODE_RX)
            self.rx_mode_active = True

    def switch_to_tx(self, payload_bytes):
        with self.lock:
            self.radio.set_mode(DummyRadio.MODE_STDBY)
            self.radio.set_mode(DummyRadio.MODE_TX)
            self.radio.write_payload(list(payload_bytes))
            # block until airtime done
            if self.is_busy():
                time.sleep(self.radio._busy_until - time.time())
            self.radio.set_mode(DummyRadio.MODE_RX)
            self.rx_mode_active = True

    def get_status(self):
        return {
            "mode":           self.radio.mode,
            "rx_mode_active": self.rx_mode_active,
            "busy":           self.is_busy()
        }

    def listen_once(self, timeout=0.1):
        self.switch_to_rx()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.radio.get_irq_flags().get("rx_done"):
                raw = self.radio.read_payload()
                return raw, {"rssi": -30, "snr": 5}
            time.sleep(0.005)
        return None, {}

    def broadcast(self, payload_bytes, timeout=0.1):
        self.switch_to_tx(payload_bytes)

    def sync(self):
        pass