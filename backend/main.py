# main.py
from pyLoRa import configure, lora_module

# Run system checks
configure.run_checks()
configure.check_gpio()
configure.check_spi()

# Create LoRa object
lora = lora_module.LoRa()

# Initialize
lora.reset()               # Optional: HW reset using GPIO
lora.set_frequency(433)    # MHz
lora.set_tx_power(14)      # dBm

# Set mode
lora.set_mode_rx()         # Standby/Receive/Transmit/etc.

data = b"Hello World"
lora.send(data)

if lora.receive():
    packet = lora.read()
    print("Received:", packet)

lora.close()
