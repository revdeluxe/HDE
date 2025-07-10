import time
from SX127x.LoRa import LoRa, MODE
from SX127x.board_config import BOARD
from utils import encode_message, decode_message, crc_score
import RPi.GPIO as GPIO
GPIO.setwarnings(False)

_setup_done = False

class LoRaSender(LoRa):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([1,0,0,0,0,0])

    def send_lora(self, msg_dict):
        raw = encode_message(msg_dict)
        self.write_payload(list(raw))
        self.set_mode(self.MODE.TX)
        # wait for TX done…
        while not self.get_irq_flags()['tx_done']:
            time.sleep(0.01)
        self.clear_irq_flags(TxDone=1)
        self.set_mode(self.MODE.SLEEP)
        return True

class LoRaReceiver(LoRa):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        BOARD.setup()
        self.set_mode(MODE.SLEEP)

    def safe_board_setup():
        global _setup_done
        if not _setup_done:
            BOARD.setup()
            _setup_done = True

    def get_status(self):
        return {
            "rssi":   self.get_rssi_value(),
            "snr":    self.get_pkt_snr_value(),
            "gain_dbi": 2.15
        }
        
    def listen_once(self, timeout=10):
        self.set_dio_mapping([0,0,0,0,0,0])  # DIO0=RxDone
        self.set_mode(self.MODE.RXCONT)
        start = time.time()
        while time.time() - start < timeout:
            if self.get_irq_flags()['rx_done']:
                self.clear_irq_flags(RxDone=1)
                payload = bytes(self.read_payload(nocheck=True))
                msg = decode_message(payload)
                quality = crc_score(payload)
                self.set_mode(self.MODE.SLEEP)
                return msg, quality
        self.set_mode(self.MODE.SLEEP)
        return None, 0
