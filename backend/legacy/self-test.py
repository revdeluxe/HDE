from SX127x.board_config import BOARD
from SX127x.LoRa        import LoRa, MODE

# 1) Init GPIO + SPI
BOARD.setup()
BOARD.SpiDev(spi_bus=0, spi_cs=0)

# 2) Stub out calibration so it wont assert
class QuickLoRa(LoRa):
    def rx_chain_calibration(self, *args, **kwargs):
        pass

# 3) Instantiate & configure
radio = QuickLoRa(verbose=True)
radio.set_mode(MODE.STDBY)
radio.set_freq(433)
radio.set_pa_config(pa_select=1, max_power=7, output_power=15)
radio.set_spreading_factor(12)

# 4) Read the VERSION register to confirm SPI talk
ver = radio.get_register(0x42)
print(f"VERSION register: 0x{ver:02X}")   # should be 0x12 for SX1278

# 5) Test basic TX/RX loopback
radio.set_mode(MODE.TX)
radio.write_payload(b"PING")
radio.set_mode(MODE.RXCONT)

# Busy-wait for DIO0 to go high (TX done)
while not radio.get_irq_flags().get("tx_done"):
    pass
radio.clear_irq_flags()
print("TX done, switching to RX")

# Busy-wait for RX
start = time.time()
while time.time() - start < 5:
    if radio.get_irq_flags().get("rx_done"):
        payload = radio.read_payload(nocheck=True)
        print("Loopback Rx:", payload)
        break
else:
    print("No loopback packet received.")
