from SX127x.board_config import BOARD
BOARD.setup()

from SX127x.LoRa import LoRa, MODE
from lora_interface import LoRaInterface

# 1) Stub out the built-in cal that trips AssertionError
class CustomLoRa(LoRa):
    def rx_chain_calibration(self, *args, **kwargs):
        print("??  Skipped RX-chain calibration")

    def __init__(self, verbose=False):
        super().__init__(verbose)
        # map DIO0 only; others left unbound
        self.set_dio_mapping([0, 0, 0, 0, 0, 0])

# 2) Instantiate and configure the radio
radio = CustomLoRa(verbose=False)
radio.set_mode(MODE.STDBY)
radio.set_freq(433)
radio.set_pa_config(pa_select=1, max_power=7, output_power=15)
radio.set_spreading_factor(12)

# 3) Wrap in your interface
lora = LoRaInterface(radio)
