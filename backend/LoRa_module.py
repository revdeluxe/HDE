from SX127x.board_config import BOARD
from SX127x.LoRa import LoRa, MODE
from lora_interface import LoRaInterface
import time

print("🔌 Initializing SX1278x LoRa")

# 1) Hardware prep
BOARD.setup()

class CustomLoRa(LoRa):
    def __init__(self, verbose=False):
        super().__init__(verbose)
        self.set_dio_mapping([0, 0, 0, 0, 0, 0])

radio = CustomLoRa(verbose=True)
radio.set_mode(MODE.STDBY)
radio.set_freq(433)
radio.set_pa_config(pa_select=1, max_power=7, output_power=15)
radio.set_spreading_factor(12)

lora = LoRaInterface(radio)
print("✅ SX1278x configured")

# 2) Test TX
try:
    payload = b"ping"
    lora.switch_to_tx(payload)
    print("📡 Sent test payload:", payload)
except Exception as e:
    print("❌ TX test failed:", e)

# 3) Test RX
try:
    lora.switch_to_rx()
    msg, quality = lora.listen_once(timeout=3)
    if msg:
        print("📥 Received response:", msg)
    else:
        print("⚠️ No response received")
except Exception as e:
    print("❌ RX test failed:", e)

print("🎯 LoRa test completed")
