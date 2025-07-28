# interface.py

import time
import json
from typing import Optional, Tuple, Dict, Any, List

from SX127x.board_config import BOARD
from SX127x.LoRa import LoRa, MODE

from utils import encode_message, decode_message

CHUNK_SIZE = 240  # max bytes per LoRa packet


def chunk_payload(payload: bytes, max_size: int = CHUNK_SIZE) -> List[bytes]:
    """
    Split a bytes payload into MTU-safe chunks.
    """
    return [payload[i : i + max_size] for i in range(0, len(payload), max_size)]


class LoRaInterface(LoRa):
    """
    LoRa wrapper for:
      - JSON-serializable dict ↔ framed bytes + CRC
      - automatic chunking for SX127x MTU
      - single-threaded IRQ polling TX/RX
      - CRC-map handshake
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
        # 1) Low-level hardware & SPI init
        BOARD.setup()
        BOARD.SpiDev(spi_bus=spi_bus, spi_cs=spi_cs)

        # 2) Base LoRa __init__ without auto-calibration
        super().__init__(verbose=verbose, do_calibration=False)

        # 3) Enter SLEEP, then optionally calibrate RX chain
        self.set_mode(MODE.SLEEP)
        time.sleep(0.05)

        if do_calibration:
            # ensure sleep mode so set_freq() calls inside calibration don't assert
            self.set_mode(MODE.SLEEP)
            time.sleep(0.05)
            super().rx_chain_calibration(True)
            # return to standby after calibration
            self.set_mode(MODE.STDBY)
            time.sleep(0.05)

        # 4) Set RF parameters
        self.set_freq(frequency)
        self.set_spreading_factor(sf)
        self.set_pa_config(
            pa_select=pa_select,
            max_power=max_power,
            output_power=output_power,
        )

        # 5) Finalize: go back to sleep until TX/RX calls
        self.set_mode(MODE.SLEEP)
        self.timeout = timeout
        self.rx_mode_active = False

    def received_flag(self) -> bool:
        """
        True if any RX-related or TX-done IRQ flags are still set.
        """
        flags = self.get_irq_flags()  # dict of flag_name: int
        return bool(
            flags.get("rx_done")
            or flags.get("rx_timeout")
            or flags.get("crc_error")
            or flags.get("tx_done")
        )

    def switch_to_rx(self, continuous: bool = True) -> None:
        """
        Enter RX mode: continuous or single-shot.
        """
        mode = MODE.RXCONT if continuous else MODE.RXSINGLE
        self.set_mode(MODE.SLEEP)
        time.sleep(0.005)
        self.set_mode(MODE.STDBY)
        self.clear_irq_flags()
        self.set_mode(mode)
        self.rx_mode_active = True

    def switch_to_tx(self, payload: bytes) -> None:
        """
        Load raw bytes into FIFO & transmit.
        Blocks until TX-done IRQ.
        """
        # wait out any pending flags
        deadline = time.time() + self.timeout
        while time.time() < deadline and self.received_flag():
            time.sleep(0.01)

        self.clear_irq_flags()
        self.set_mode(MODE.STDBY)
        self.write_payload(list(payload))
        self.set_mode(MODE.TX)

        # wait for DIO0 TX-done
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            flags = self.get_irq_flags()
            if flags.get("tx_done"):
                break
            time.sleep(0.001)

        self.clear_irq_flags(TxDone=1)
        self.set_mode(MODE.STDBY)

    def send(self, msg: Dict[str, Any]) -> None:
        """
        High-level send: dict → framed bytes → chunk → TX.
        """
        raw = encode_message(msg)
        for chunk in chunk_payload(raw):
            self.switch_to_tx(chunk)
            time.sleep(0.05)

    def listen_once(
        self,
    ) -> Tuple[Optional[int], Optional[bytes], Dict[str, float]]:
        """
        Single-shot RX: wait up to self.timeout. Returns:
          (seq_id, raw_bytes, {rssi, snr})
        or (None, None, {}).
        """
        self.switch_to_rx(continuous=False)
        start = time.time()

        while time.time() - start < self.timeout:
            flags = self.get_irq_flags()
            if flags.get("rx_done"):
                self.clear_irq_flags()
                raw = bytes(self.read_payload(nocheck=True))
                seq = raw[0]
                data = raw[1:]
                return seq, data, {
                    "rssi": self.get_rssi(),
                    "snr": self.get_snr(),
                }
            time.sleep(0.01)

        return None, None, {}

    def on_receive(self, raw: bytes) -> Dict[str, Any]:
        """
        Decode raw bytes (after seq-byte strip) into a Python dict.
        """
        return decode_message(raw)

    def broadcast(self, payload: bytes, listen_after: bool = False):
        """
        Fire-and-forget raw bytes. Optionally listen once.
        """
        self.switch_to_tx(payload)
        if listen_after:
            return self.listen_once()

    def initiate_handshake(self, my_hostname: str = "node-A") -> Optional[str]:
        """
        Send HANDSHAKE_REQ, wait for HANDSHAKE_ACK, return peer hostname.
        """
        req = {
            "type": "HANDSHAKE_REQ",
            "from": my_hostname,
            "timestamp": int(time.time()),
        }
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
        Operator-friendly status snapshot.
        """
        return {
            "rx_mode_active": self.rx_mode_active,
            "rssi": self.get_rssi(),
            "snr": self.get_snr(),
        }

    def request_remote_crc_map(self) -> Dict[int, int]:
        """
        Send “CRC_REQUEST” then wait for JSON reply {id:crc,…}.
        Raises TimeoutError on no or invalid response.
        """
        self.switch_to_tx(b"CRC_REQUEST")
        _, raw, _ = self.listen_once()
        if not raw:
            raise TimeoutError("No CRC-map response received")

        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError as e:
            raise RuntimeError(f"Invalid CRC-map JSON: {e}")

    def send_crc_map(self, crc_map: Dict[int, int]) -> None:
        """
        Reply to CRC_REQUEST by sending your CRC map as JSON.
        """
        payload = json.dumps(crc_map).encode("utf-8")
        self.switch_to_tx(payload)
