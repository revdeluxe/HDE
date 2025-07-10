import time
import RPi.GPIO as GPIO
from SX127x.LoRa       import LoRa, MODE
from SX127x.board_config import BOARD
from utils             import encode_message, decode_message, crc_score

GPIO.setwarnings(False)

# --- One-time board setup ---------------------------------------------
_setup_done = False
def safe_board_setup():
    global _setup_done
    if not _setup_done:
        BOARD.setup()
        _setup_done = True

# --- Sender ------------------------------------------------------------
class LoRaSender(LoRa):
    def __init__(self, **kwargs):
        safe_board_setup()        # ? only first call will actually run BOARD.setup()
        super().__init__(**kwargs) 
        self.set_mode(MODE.SLEEP) # use the imported MODE, not self.MODE
        self.set_dio_mapping([1,0,0,0,0,0])

    def send_lora(self, msg_dict):
        raw = encode_message(msg_dict)
        self.write_payload(list(raw))
        self.set_mode(MODE.TX)
        while not self.get_irq_flags()['tx_done']:
            time.sleep(0.01)
        self.clear_irq_flags(TxDone=1)
        self.set_mode(MODE.SLEEP)
        return True

# --- Receiver ---------------------------------------------------------
class LoRaReceiver(LoRa):
    def __init__(self, **kwargs):
        safe_board_setup()        
        super().__init__(**kwargs)
        self.set_mode(MODE.SLEEP)

    def get_status(self):
        return {
            "rssi":     self.get_rssi_value(),
            "snr":      self.get_pkt_snr_value(),
            "gain_dbi": 2.15
        }

    def listen_once(self, timeout=10):
        self.set_dio_mapping([0,0,0,0,0,0])
        self.set_mode(MODE.RXCONT)
        start = time.time()
        while time.time() - start < timeout:
            if self.get_irq_flags()['rx_done']:
                self.clear_irq_flags(RxDone=1)
                payload = bytes(self.read_payload(nocheck=True))
                msg     = decode_message(payload)
                q       = crc_score(payload)
                self.set_mode(MODE.SLEEP)
                return msg, q
        self.set_mode(MODE.SLEEP)
        return None, 0
