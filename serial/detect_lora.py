from time import sleep
from SX127x.LoRa import *
from SX127x.board_config import BOARD

# LORA SX1278 board configuration and simple alive loop example
# Requires: pyLoRa library (pip install pyLoRa)


# Board setup
BOARD.setup()

class LoRaConfig(LoRa):
    def __init__(self, verbose=False):
        super(LoRaConfig, self).__init__(verbose)
        # SX1278 typical config
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([0]*6)
        self.set_freq(433)  # Set frequency to 433MHz
        self.set_pa_config(pa_select=1)
        self.set_bw(BW.BW125)
        self.set_spreading_factor(7)
        self.set_coding_rate(CODING_RATE.CR4_5)
        self.set_preamble(8)
        self.set_sync_word(0x12)
        self.set_rx_crc(True)

if __name__ == '__main__':
    lora = LoRaConfig(verbose=False)
    lora.set_mode(MODE.STDBY)
    print("LoRa SX1278 initialized. Entering alive loop...")
    try:
        while True:
            print("LoRa is alive...")
            sleep(2)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        BOARD.teardown()