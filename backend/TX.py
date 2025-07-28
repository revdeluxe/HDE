from SX127x.LoRa import LoRa, MODE
from SX127x.board_config import BOARD
import time

BOARD.setup(cls=BOARD)
BOARD.SpiDev(spi_bus=0, spi_cs=0)
lora = LoRa(verbose=False, do_calibration=True)

lora.set_mode(MODE.STDBY)
lora.set_freq(433e6)
lora.set_spreading_factor(7)
lora.set_pa_config(pa_select=1, max_power=7, output_power=15)
lora.set_mode(MODE.SLEEP)

# TX loop
lora.set_mode(MODE.STDBY)
lora.write_payload([0x01,0x02,0x03,0x04])
lora.set_mode(MODE.TX)
time.sleep(1)
print("Done TX")
