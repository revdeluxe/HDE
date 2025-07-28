# interface.py

import time
from typing import Optional, Tuple, Dict, Any
from SX127x.board_config import BOARD
from SX127x.LoRa import LoRa, MODE
from utils import encode_message, decode_message, encode_chunks

CHUNK_SIZE = 240
def chunk_payload(payload: bytes, size: int = CHUNK_SIZE) -> list[bytes]:
    """
    Split a bytes payload into fixed-size chunks, prefixing each with a sequence ID.
    Internally uses encode_chunks() from utils.
    """
    return encode_chunks(payload, chunk_size=size)

class LoRaInterface(LoRa):
    """
    A LoRa radio with:
      - manual RX-chain calibration
      - safe sleep/standby/freq transitions
      - chunked payload send/receive
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
        # Board & SPI setup
        BOARD.setup()
        BOARD.SpiDev(spi_bus=spi_bus, spi_cs=spi_cs)

        # Initialize without auto‐calibration
        super().__init__(verbose=verbose, do_calibration=False)

        # Clean mode transition + manual calibration
        self.set_mode(MODE.SLEEP)
        time.sleep(0.05)
        if do_calibration:
            # pass the float you just got, not the base-class method
            super().rx_chain_calibration(frequency)

        # RF parameters
        self.set_freq(frequency)
        self.set_pa_config(
            pa_select=pa_select,
            max_power=max_power,
            output_power=output_power,
        )
        self.set_spreading_factor(sf)

        # Sleep until used
        self.set_mode(MODE.SLEEP)

        # RX timeout for listen_once()
        self.timeout = timeout
        self.rx_mode_active = False

    def calibration_freq(self) -> float:
        """
        Return the frequency used for RX chain calibration.
        Default is 433 MHz, but can be overridden.
        """
        return 433e6

    def set_freq(self, freq_hz: float) -> None:
        """
        Guarded frequency setter: always moves through STDBY first.
        """
        if self.mode not in (MODE.SLEEP, MODE.STDBY, MODE.FSK_STDBY):
            self.set_mode(MODE.STDBY)
            time.sleep(0.02)
        super().set_freq(freq_hz)

    def switch_to_rx(self, continuous: bool = True) -> None:
        """
        Prepare the radio for RX (single or continuous).
        """
        mode = MODE.RXCONT
        self.set_mode(MODE.SLEEP)
        time.sleep(0.005)
        self.set_mode(MODE.STDBY)
        self.set_mode(mode)
        self.rx_mode_active = True

    def switch_to_tx(self, payload: bytes) -> None:
        """
        Load a payload and fire off a TX.
        Blocks until TxDone.
        """
        self.set_mode(MODE.STDBY)
        self.write_payload(list(payload))
        self.set_mode(MODE.TX)

        # wait for TX-done on DIO0
        while not self.received_flag():
            time.sleep(0.001)
        self.clear_irq_flags(TxDone=1)

    def send(self, msg: dict[str, Any]) -> None:
        """
        1) JSON→bytes via utils.encode_message()
        2) chunk_payload()
        3) TX each packet, brief spacing
        """
        payload = encode_message(msg)
        for chunk in chunk_payload(payload):
            self.switch_to_tx(chunk)
            time.sleep(0.1)

    def listen_once(self) -> Tuple[Optional[int], Optional[bytes], Dict[str, float]]:
        """
        Switch to single-RX, wait up to self.timeout seconds.
        Returns (seq_idx, raw_payload, meta), or (None, None, {}).
        """
        self.switch_to_rx(continuous=False)
        start = time.time()

        while (time.time() - start) < self.timeout:
            flags = self.get_irq_flags()
            if flags.get("rx_done"):
                self.clear_irq_flags()
                raw = self.read_payload(nocheck=True)
                seq_id = raw[0]
                data_bytes = raw[1:]
                return (
                    seq_id,
                    data_bytes,
                    {"rssi": self.get_rssi(), "snr": self.get_snr()},
                )
            time.sleep(0.01)

        return None, None, {}

    def on_receive(self, data: bytes) -> dict:
        """
        Raw bytes → Python dict via utils.decode_message()
        """
        return decode_message(data)

    def broadcast(self, payload: bytes, listen_after: bool = False):
        """
        Fire & forget, or optionally listen once afterwards.
        """
        self.switch_to_tx(payload)
        if listen_after:
            return self.listen_once()

    def initiate_handshake(self, my_hostname: str = "node-A") -> Optional[str]:
        """
        Send a HANDSHAKE_REQ, await a HANDSHAKE_ACK, return peer hostname.
        """
        req = encode_message(
            {"type": "HANDSHAKE_REQ", "from": my_hostname, "timestamp": int(time.time())}
        )
        self.switch_to_tx(req)

        seq, payload, _meta = self.listen_once()
        if payload:
            resp = decode_message(payload)
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

    def get_status(self) -> dict:
        """
        Operator-friendly status dict.
        """
        return {
            "rx_mode_active": self.rx_mode_active,
            "rssi": self.get_rssi(),
            "snr": self.get_snr(),
        }

    while True:
        with STATUS_LOCK:
            latest_status.clear()
            latest_flags.clear()
            latest_status.update(radio.get_status())
            latest_flags.update(radio.get_irq_flags())

        
        time.sleep(0.01)

