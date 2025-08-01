import threading
import queue
import time
from pyLoRa.lora_module import LoRa as lora_module

class LoRaEngine:
    def __init__(self):
        self.lora = lora_module()
        self.state = "idle"
        self.lock = threading.Lock()
        self.message_queue = queue.Queue()
        self.running = True

        # Start state handler thread
        self.worker = threading.Thread(target=self._loop, daemon=True)
        self.worker.start()

    def _loop(self):
        while self.running:
            with self.lock:
                state = self.state

            if state == "reset":
                self._do_reset()
            elif state == "transmit":
                self._do_transmit()
            elif state == "receive":
                self._do_receive()
            elif state == "idle":
                time.sleep(0.1)
            else:
                print(f"[LoRaEngine] Unknown state: {state}")
                self.set_state("idle")
                time.sleep(0.1)

    def _do_reset(self):
        print("[LoRaEngine] Resetting...")
        self.lora.reset()
        self.set_state("idle")

    def _do_receive(self):
        self.lora.set_mode_rx()
        if self.lora.received_packet():
            raw = self.lora.read_payload()
            print("[LoRaEngine] Received:", raw)
            self.message_queue.put(raw)
        time.sleep(0.2)

    def _do_transmit(self):
        try:
            message = self.message_queue.get(timeout=1)
        except queue.Empty:
            self.set_state("idle")
            return
        self.lora.set_mode_tx()
        self.lora.write_payload(message.encode())
        print("[LoRaEngine] Sent:", message)
        time.sleep(0.5)
        self.set_state("receive")  # Auto-switch back to RX

    def set_state(self, new_state):
        with self.lock:
            self.state = new_state

    def get_state(self):
        with self.lock:
            return self.state

    def queue_message(self, msg):
        self.message_queue.put(msg)
        self.set_state("transmit")

    def get_messages(self):
        items = []
        while not self.message_queue.empty():
            items.append(self.message_queue.get())
        return items

    def shutdown(self):
        self.running = False
        self.worker.join()
