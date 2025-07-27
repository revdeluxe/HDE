# interface.py

import time
from SX127x.board_config import BOARD
from SX127x.LoRa import LoRa, MODE
from utils import encode_message, decode_message

# Maximum payload per LoRa packet (~240 bytes)
CHUNK_SIZE = 240


class CustomLoRa(LoRa):
    def __init__(self, verbose=False, do_calibration=True):
        # 1. Base init WITHOUT auto‐calibration
        super().__init__(verbose=verbose, do_calibration=False)

        # 2. Force a clean mode transition
        self.set_mode(MODE.SLEEP)
        time.sleep(0.05)
        self.set_mode(MODE.STDBY)
        time.sleep(0.05)

        # 3. Run RX‐chain calibration manually (at the right freq)
        if do_calibration:
            super().rx_chain_calibration(self.calibration_freq)

        # 4. Finish in STDBY with default DIO mapping
        self.set_mode(MODE.STDBY)
        self.set_dio_mapping([0] * 6)

    # Guard set_freq so we never violate the sleep/standby precondition
    def set_freq(self, freq_hz):
        if self.mode not in (MODE.SLEEP, MODE.STDBY, MODE.FSK_STDBY):
            self.set_mode(MODE.STDBY)
            time.sleep(0.02)
        super().set_freq(freq_hz)


def radio_init(
    spi_bus=0,
    spi_cs=0,
    freq=433e6,
    sf=12,
    pa_select=1,
    max_power=7,
    output_power=15,
    verbose=False
):
    # 1. Bring up board and SPI
    BOARD.setup()
    BOARD.SpiDev(spi_bus=spi_bus, spi_cs=spi_cs)

    # 2. Instantiate and calibrate our CustomLoRa
    radio = CustomLoRa(verbose=verbose, do_calibration=True)

    # 3. Tune RF parameters
    radio.set_freq(freq)
    radio.set_pa_config(
        pa_select=pa_select,
        max_power=max_power,
        output_power=output_power
    )
    radio.set_spreading_factor(sf)

    # 4. Sleep until first use
    radio.set_mode(MODE.SLEEP)
    return radio


class LoRaInterface:
    def __init__(self, radio=None, timeout=5.0):
        self.radio = radio or radio_init()
        self.timeout = timeout
        self.rx_mode_active = False

    def switch_to_rx(self, continuous=True):
        mode = MODE.RXCONT if continuous else MODE.RX_SINGLE
        self.radio.set_mode(MODE.SLEEP)
        time.sleep(0.005)
        self.radio.set_mode(MODE.STDBY)
        self.radio.set_mode(mode)
        self.rx_mode_active = True

    def switch_to_tx(self, payload_bytes):
        self.radio.set_mode(MODE.STDBY)
        self.radio.write_payload(payload_bytes)
        self.radio.set_mode(MODE.TX)

        # wait for TX‐done on DIO0
        while not self.radio.received_flag():
            time.sleep(0.001)
        self.radio.clear_irq_flags(TxDone=1)

    def send(self, message: bytes):
        chunks = [
            message[i : i + CHUNK_SIZE]
            for i in range(0, len(message), CHUNK_SIZE)
        ]
        for idx, chunk in enumerate(chunks):
            packet = encode_message(idx, chunk)
            self.switch_to_tx(packet)
            # resume RX if desired, or just sleep
            self.switch_to_rx()
            time.sleep(0.02)

    def listen_once(self):
        self.switch_to_rx(continuous=False)
        start = time.time()
        while (time.time() - start) < self.timeout:
            flags = self.radio.get_irq_flags()
            if flags.get("rx_done"):
                self.radio.clear_irq_flags()
                raw = self.radio.read_payload(nocheck=True)
                idx, payload = decode_message(raw)
                return idx, payload, {
                    "rssi": self.get_rssi(),
                    "snr": self.get_snr()
                }
            time.sleep(0.01)
        return None, None, {}

    def broadcast(self, payload_bytes, listen_after=False):
        self.switch_to_tx(payload_bytes)
        if listen_after:
            return self.listen_once()

    def initiate_handshake(self, my_hostname="node-A"):
        req = encode_message({
            "type": "HANDSHAKE_REQ",
            "from": my_hostname,
            "timestamp": int(time.time())
        })
        self.switch_to_tx(req)
        idx, payload, meta = self.listen_once()
        try:
            msg = decode_message(payload)
            if msg.get("type") == "HANDSHAKE_ACK":
                print(f"Handshake confirmed with {msg['from']}")
                return msg["from"]
        except Exception:
            pass
        return None

    def get_rssi(self):
        raw = self.radio.get_register(0x1A)
        return -137 + raw if raw < 256 else None

    def get_snr(self):
        raw = self.radio.get_register(0x1B)
        # signed 8‐bit value
        val = raw if raw < 128 else raw - 256
        return val / 4.0

    def get_status(self):
        return {
            "rx_mode_active": self.rx_mode_active,
            "rssi": self.get_rssi(),
            "snr": self.get_snr()
        }
