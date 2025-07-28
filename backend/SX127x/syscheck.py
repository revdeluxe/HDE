import spidev

BOARD.spi = spidev.SpiDev()
BOARD.spi.open(0, 0)  # Bus 0, Device 0
BOARD.spi.max_speed_hz = 5000000
