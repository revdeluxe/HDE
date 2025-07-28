# interface.py

import time
import json
from typing import Optional, Tuple, Dict, Any

from SX127x.board_config import BOARD
from SX127x.LoRa import LoRa, MODE

from utils import (
    encode_message,
    decode_message,
    encode_chunks,
)

class LoRaInterface(LoRa):
    """
    LoRa wrapper that packs JSON dicts into binary frames + CRC,
    chunks them for SX127x MTU, and handles single‐threaded TX/RX.
    """

    def __init__(
        self,
        spi_bus: int = 0,
        spi_cs:  int = 0,
        frequency: float = 433e6,
        sf: int = 7,
        pa_select: int = 1,
        max_power: int = 7,
        output_power: int = 15,
        timeout: float = 5.0,
        verbose: bool = False,
        do_calibration: bool = True,
    ):
        # Hardware init
        BOARD.setup()
        BOARD.SpiDev(spi_bus=spi_bus, spi_cs=spi_cs)

        super().__init__(verbose=verbose, do_calibration=False)

        # Sleep → Standby → optional calibration
        self.set_mode(MODE.SLEEP)
        time.sleep(0.05)
        if do_calibration:
            super().rx_chain_calibration(frequency)

        # RF params
        self.set_freq(frequency)
        self.set_spreading_factor(sf)
        self.set_pa_config(
            pa_select=pa_select,
            max_power=max_power,
            output_power=output_power,
        )

        # Final mode & settings
        self.set_mode(MODE.SLEEP)
        self.timeout = timeout
        self.rx_mode_active = False

    def received_flag(self) -> bool:
        """
        Returns True if any RX‐related IRQ flags are set.
        """
        flags = self.get_irq_flags()  # returns a dict
        return bool(
            flags.get("rx_done") or
            flags.get("rx_timeout") or
            flags.get("crc_error")
        )

    def switch_to_rx(self, continuous: bool = True) -> None:
        """
        Enter RX mode (single or continuous).
        """
        mode = MODE.RXCONT if continuous else MODE.RX
        self.set_mode(MODE.SLEEP)
        time.sleep(0.005)
        self.set_mode(MODE.STDBY)
        self.set_mode(mode)
        self.rx_mode_active = True

    def switch_to_tx(self, payload: bytes) -> None:
        """
        Load raw bytes into FIFO and transmit.
        Blocks until TX‐done IRQ is raised.
        """
        # clear any pending RX flags
        self.clear_irq_flags()

        # go to Standby, write FIFO, then TX
        self.set_mode(MODE.STDBY)
        self.write_payload(list(payload))
        self.set_mode(MODE.TX)

        # wait for DIO0 “TX done”
        while True:
            flags = self.get_irq_flags()
            if flags.get("tx_done"):
                break
            time.sleep(0.001)

        # clear TX flag and return to standby
        self.clear_irq_flags(TxDone=1)
        self.set_mode(MODE.STDBY)

    def send(self, msg: Dict[str, Any]) -> None:
        """
        High-level send: dict → binary → chunks → TX each.
        """
        payload = encode_message(msg)
        for chunk in encode_chunks(payload):
            self.switch_to_tx(chunk)
            time.sleep(0.05)

    def listen_once(self) -> Tuple[Optional[int], Optional[bytes], Dict[str, float]]:
        """
        Single‐shot RX: wait up to self.timeout. Returns:
          (seq_id, raw_bytes, {rssi, snr})
        or (None, None, {}).
        """
        self.switch_to_rx(continuous=False)
        start = time.time()

        while time.time() - start < self.timeout:
            flags = self.get_irq_flags()
            if flags.get("rx_done"):
                self.clear_irq_flags()
                raw = self.read_payload(nocheck=True)
                seq = raw[0]
                data = raw[1:]
                return seq, data, {
                    "rssi": self.get_rssi(),
                    "snr":  self.get_snr(),
                }
            time.sleep(0.01)

        return None, None, {}

    def on_receive(self, raw: bytes) -> Dict[str, Any]:
        """
        Decode raw bytes into Python dict via your framing + CRC.
        """
        return decode_message(raw)

    def broadcast(self, payload: bytes, listen_after: bool = False):
        """
        Fire‐and‐forget raw bytes, optionally listen once.
        """
        self.switch_to_tx(payload)
        if listen_after:
            return self.listen_once()

    def initiate_handshake(self, my_id: str) -> Optional[str]:
        """
        Send HANDSHAKE_REQ, wait for HANDSHAKE_ACK, return peer ID.
        """
        req = {"type":"HANDSHAKE_REQ", "from":my_id, "timestamp":int(time.time())}
        self.send(req)

        seq, raw, _ = self.listen_once()
        if raw:
            resp = decode_message(raw)
            if resp.get("type") == "HANDSHAKE_ACK":
                return resp.get("from")
        return None

    def get_rssi(self) -> Optional[float]:
        raw = self.get_register(0x1A)
        return (-137 + raw) if raw < 256 else None

    def get_snr(self) -> Optional[float]:
        raw = self.get_register(0x1B)
        val = raw if raw < 128 else raw - 256
        return val / 4.0

    def get_status(self) -> Dict[str, Any]:
        """
        Snapshot for your /api/status endpoint.
        """
        return {
            "rx_mode_active": self.rx_mode_active,
            "rssi":           self.get_rssi(),
            "snr":            self.get_snr(),
        }

    def request_remote_crc_map(self) -> Dict[int, int]:
        """
        Send CRC_REQUEST and await JSON map {id:crc}. Raises on timeout.
        """
        # dispatch a raw “CRC_REQUEST” frame
        self.switch_to_tx(b"CRC_REQUEST")
        seq, raw, _ = self.listen_once()
        if raw:
            return json.loads(raw.decode())
        raise TimeoutError("No CRC response")

    def send_crc_map(self, crc_map: Dict[int, int]) -> None:
        """
        Reply to a CRC_REQUEST by broadcasting your CRC map.
        """
        payload = json.dumps(crc_map).encode()
        self.switch_to_tx(payload)
