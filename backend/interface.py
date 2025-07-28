# interface.py

import time
import json
from typing import Optional, Tuple, Dict, Any, List

from SX127x.board_config import BOARD
from SX127x.LoRa import LoRa, MODE

from utils import encode_message, decode_message

CHUNK_SIZE = 240  # maximum raw payload per LoRa packet
def chunk_payload(payload: bytes, max_size: int = 64) -> list[dict]:
    chunks = []
    for i in range(0, len(payload), max_size):
        fragments = payload[i:i + max_size]
        chunks.append({"data": fragments})
    return chunks

class LoRaInterface(LoRa):
    """
    A LoRa wrapper that:
      - sends/receives JSON-serializable dicts
      - splits large payloads into MTU-safe chunks
      - enforces single-threaded TX/RX with IRQ-flag polling
      - supports a CRC-sync handshake for map exchange
    """

    def __init__(
        self,
        spi_bus: int = 0,
        spi_cs: int = 0,
        frequency: float = 433e6,
        sf: int = 7,
        pa_select: int = 1,
        max_power: int = 7,
        output_power: int = 15,
        timeout: float = 5.0,
        verbose: bool = False,
        do_calibration: bool = True,
    ):
        # --- Hardware & SPI setup ---
        BOARD.setup()
        BOARD.SpiDev(spi_bus=spi_bus, spi_cs=spi_cs)

        # Initialize without auto-calibration
        super().__init__(verbose=verbose, do_calibration=False)

        # Sleep → optional RX chain calibration → standby
        self.set_mode(MODE.SLEEP)
        time.sleep(0.05)
        if do_calibration:
            super().rx_chain_calibration(frequency)

        # RF parameters
        self.set_freq(frequency)
        self.set_spreading_factor(sf)
        self.set_pa_config(
            pa_select=pa_select, max_power=max_power, output_power=output_power
        )

        # Final mode & state
        self.set_mode(MODE.SLEEP)
        self.timeout = timeout
        self.rx_mode_active = False

    def received_flag(self) -> bool:
        """
        Return True if any RX-related or TX-done IRQ flags are still set.
        """
        flags = self.get_irq_flags()  # returns a dict of flag_name: int
        return bool(
            flags.get("rx_done")
            or flags.get("rx_timeout")
            or flags.get("crc_error")
            or flags.get("tx_done")
        )

    def switch_to_rx(self, continuous: bool = True) -> None:
        """
        Put the radio into RX mode. If continuous is False, listen_once() will stop after one packet.
        """
        mode = MODE.RXCONT if continuous else MODE.RX
        self.set_mode(MODE.SLEEP)
        time.sleep(0.005)
        self.set_mode(MODE.STDBY)
        self.clear_irq_flags()  # ensure clean slate
        self.set_mode(mode)
        self.rx_mode_active = True

    def switch_to_tx(self, payload: bytes) -> None:
        """
        Load a bytes payload into FIFO and transmit. Blocks until TX-done.
        """
        # Wait out any lingering RX flags
        deadline = time.time() + self.timeout
        while time.time() < deadline and self.received_flag():
            time.sleep(0.01)

        # Clear IRQs, go to standby, write payload, then TX
        self.clear_irq_flags()
        self.set_mode(MODE.STDBY)
        self.write_payload(list(payload))
        self.set_mode(MODE.TX)

        # Wait for TX-done on DIO0
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            flags = self.get_irq_flags()
            if flags.get("tx_done"):
                break
            time.sleep(0.001)

        # Clear TX-done flag, return to standby
        self.clear_irq_flags(TxDone=1)
        self.set_mode(MODE.STDBY)

    def send(self, msg: Dict[str, Any]) -> None:
        """
        High-level send: dict → JSON+CRC bytes → chunks → TX each chunk.
        """
        raw = encode_message(msg)
        for chunk in chunk_payload(raw):
            self.switch_to_tx(chunk)
            time.sleep(0.05)

    def listen_once(
        self,
    ) -> Tuple[Optional[int], Optional[bytes], Dict[str, float]]:
        """
        Wait up to self.timeout for one packet. Returns:
          (sequence_id, raw_bytes, {'rssi':…, 'snr':…})
        or (None, None, {}).
        """
        self.switch_to_rx(continuous=False)
        start = time.time()

        while (time.time() - start) < self.timeout:
            flags = self.get_irq_flags()
            if flags.get("rx_done"):
                # packet received
                self.clear_irq_flags()
                raw = bytes(self.read_payload(nocheck=True))
                seq = raw[0]
                data = raw[1:]
                return seq, data, {"rssi": self.get_rssi(), "snr": self.get_snr()}
            time.sleep(0.01)

        # timed out
        return None, None, {}

    def on_receive(self, raw: bytes) -> Dict[str, Any]:
        """
        Decode a raw payload (after stripping seq byte) into the original dict.
        """
        return decode_message(raw)

    def broadcast(self, payload: bytes, listen_after: bool = False):
        """
        Send raw bytes without framing. Optionally do a single listen afterward.
        """
        self.switch_to_tx(payload)
        if listen_after:
            return self.listen_once()

    def initiate_handshake(self, my_hostname: str = "node-A") -> Optional[str]:
        """
        Send HANDSHAKE_REQ, then listen for HANDSHAKE_ACK. Return peer hostname or None.
        """
        req = {"type": "HANDSHAKE_REQ", "from": my_hostname, "timestamp": int(time.time())}
        self.send(req)

        seq, raw, _ = self.listen_once()
        if raw:
            resp = decode_message(raw)
            if resp.get("type") == "HANDSHAKE_ACK":
                return resp.get("from")
        return None

    def get_rssi(self) -> Optional[float]:
        raw = self.get_register(0x1A)
        return -137 + raw if raw < 256 else None

    def get_snr(self) -> Optional[float]:
        raw = self.get_register(0x1B)
        val = raw if raw < 128 else raw - 256
        return val / 4.0

    def get_status(self) -> Dict[str, Any]:
        """
        A snapshot of radio state for external status APIs.
        """
        return {
            "rx_mode_active": self.rx_mode_active,
            "rssi": self.get_rssi(),
            "snr": self.get_snr(),
        }

    def request_remote_crc_map(self) -> Dict[int, int]:
        """
        Ask the remote node for its CRC map. Sends a raw 'CRC_REQUEST'
        then waits for a JSON response {id: crc, ...}.
        """
        # send the magic request
        self.switch_to_tx(b"CRC_REQUEST")

        # wait for JSON reply
        _, raw, _ = self.listen_once()
        if raw:
            try:
                return json.loads(raw.decode("utf-8"))
            except ValueError as e:
                raise RuntimeError(f"Invalid CRC-map JSON: {e}")
        else:
            raise TimeoutError("No CRC-map response received")

    def send_crc_map(self, crc_map: Dict[int, int]) -> None:
        """
        On slave: respond to a CRC_REQUEST by transmitting your CRC map.
        """
        payload = json.dumps(crc_map).encode("utf-8")
        self.switch_to_tx(payload)
