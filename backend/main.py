# main.py
from flask import Flask, request, jsonify
import json
import time
import queue
import threading

from utils import encode_message, decode_message, crc_score
# from LoRa_test import DummyLoRaInterface
from LoRa_module import LoRaInterface  # Replace with actual LoRa interface import
from SX127x.LoRa import LoRa, MODE
from SX127x.board_config import BOARD
# —————————————————————————————————————————————
# Use DummyLoRaInterface for testing (no SPI/GPIO)
tx_queue = queue.Queue()
BOARD.setup()
class CustomLoRa(LoRa):
    def __init__(self, verbose=False):
        super().__init__(verbose)
        self.set_dio_mapping([0, 0, 0, 0, 0, 0])

radio = CustomLoRa(verbose=False)
radio.set_mode(MODE.STDBY)
radio.set_freq(433)
radio.set_pa_config(pa_select=1, max_power=7, output_power=15)
radio.set_spreading_factor(12)

lora = LoRaInterface(radio)

# LoRa MTU (~240 bytes), split large payloads into chunks
CHUNK_SIZE = 240

def chunk_payload(payload: bytes, size: int = CHUNK_SIZE):
    """Split a bytes payload into fixed-size chunks."""
    return [payload[i : i + size] for i in range(0, len(payload), size)]

def tx_worker():
    """Background thread: pull from tx_queue ➔ send via dummy LoRa."""
    while True:
        chunk = tx_queue.get()
        try:
            if tx_queue.qsize() % 10 == 0:
                print(f"[TX Worker] queue depth: {tx_queue.qsize()}")
            lora.switch_to_tx(chunk)
        except Exception as e:
            print("[TX Worker] Error sending:", e)
        finally:
            time.sleep(0.1)

# start daemon
threading.Thread(target=tx_worker, daemon=True).start()

# —————————————————————————————————————————————
app = Flask(__name__)

@app.route('/api/send', methods=['POST'])
def api_send():
    """
    POST {"from":"alice","message":"hello"}
    Encodes, chunks, queues for TX. Returns total byte count queued.
    """
    data = request.get_json() or {}
    if 'from' not in data or 'message' not in data:
        return jsonify({"error": "Missing 'from' or 'message'"}), 400

    # 1) Build & encode
    msg     = {'from': data['from'], 'message': data['message']}
    payload = encode_message(msg)

    # 2) Chunk & queue
    for chunk in chunk_payload(payload):
        tx_queue.put(chunk)

    return jsonify({"status": "queued", "bytes": len(payload)}), 202

@app.route('/api/receive', methods=['GET'])
def api_receive():
    """
    Listen once (timeout=5s). Decode & score payload if present.
    """
    try:
        payload, _ = lora.listen_once(timeout=5)
        if not payload:
            return jsonify({"error": "No message received"}), 404

        decoded = decode_message(payload)
        score   = crc_score(payload)
        return jsonify({"message": decoded, "quality": score}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def api_status():
    """Quick status: RX mode flag + TX queue depth."""
    status = lora.get_status()
    return jsonify({
        "rx_mode":        status["rx_mode_active"],
        "tx_queue_depth": tx_queue.qsize(),
        "busy":           status["busy"]
    }), 200

@app.route('/api/broadcast', methods=['POST'])
def api_broadcast():
    """
    Immediately TX a raw JSON envelope (no queue).
    """
    data = request.get_json() or {}
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    payload = json.dumps(data).encode()
    try:
        lora.switch_to_tx(payload)
        return jsonify({"status": "broadcasted"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync', methods=['POST'])
def api_sync():
    """
    Fire off whatever lora.sync() does.
    """
    try:
        lora.sync()
        return jsonify({"status": "synchronized"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def api_health():
    """Liveness probe."""
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    print("Starting Dummy-LoRa backend API on port 5000…")
    app.run(host='0.0.0.0', port=5000, debug=True)
