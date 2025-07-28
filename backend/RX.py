from SX127x.LoRa import LoRa, MODE
from SX127x.board_config import BOARD
import time

BOARD.setup(cls=BOARD)
BOARD.SpiDev(spi_bus=0)
lora = LoRa(verbose=False, do_calibration=True)

lora.set_mode(MODE.STDBY)
lora.set_freq(433e6)
lora.set_spreading_factor(7)
lora.set_pa_config(pa_select=1, max_power=7, output_power=15)
lora.set_mode(MODE.RXCONT)

start = time.time()
while time.time()-start<5:
    flags = lora.get_irq_flags()
    if flags.get("rx_done"):
        raw = bytes(lora.read_payload(nocheck=True))
        print("Got raw:", raw)
        break
    time.sleep(0.01)
else:
    print("No RX")

