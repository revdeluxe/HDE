# main.py
from flask import Flask, request, jsonify
import queue, threading, time, socket, utils
from interface        import LoRaInterface
from SX127x.LoRa        import LoRa, MODE
from SX127x.board_config import BOARD
from utils import encode_message, decode_message, crc_score
from threading import Lock

sync_queue = []
sync_lock = Lock()

tx_queue = queue.Queue()
BOARD.setup()
BOARD.SpiDev(spi_bus=0, spi_cs=0)

class CustomLoRa(LoRa):
    def __init__(self, verbose=False):
        LoRa.__init__(self, verbose=False, do_calibration=True)
        self.set_mode(MODE.STDBY)
        self.set_dio_mapping([0, 0, 0, 0, 0, 0])


radio = CustomLoRa(verbose=False)
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
            
synced_messages = []

# start daemon
threading.Thread(target=tx_worker, daemon=True).start()

# —————————————————————————————————————————————
app = Flask(__name__)

@app.before_first_request
def boot_beacon():
    lora.switch_to_tx(b"BOOT_OK")
    
def store_synced_message(msg, source="remote"):
    if not isinstance(msg, dict):
        return
    entry = {
        "from": msg.get("from"),
        "message": msg.get("message"),
        "timestamp": msg.get("timestamp", int(time.time())),
        "source": source,
        "status": "synced"
    }
    synced_messages.append(entry)


@app.route('/api/send', methods=['POST'])
def api_send():
    global last_sent_msg
    data = request.get_json() or {}
    if 'from' not in data or 'message' not in data:
        return jsonify({"error": "Missing 'from' or 'message'"}), 400

    msg     = {'from': data['from'], 'message': data['message'], 'timestamp': data.get('timestamp')}
    payload = encode_message(msg)

    for chunk in chunk_payload(payload):
        tx_queue.put(chunk)

    last_sent_msg = msg  # store locally

    # ?? Immediately log it as received (local sync)
    store_synced_message(msg, source='local')

    return jsonify({"status": "queued", "bytes": len(payload)}), 202
    
@app.route('/api/messages/<source>', methods=['GET'])
def api_messages_by_source(source):
    filtered = [m for m in synced_messages if m["source"] == source]
    return jsonify(filtered[-50:]), 200

def handshake_listener():
    while True:
        lora.switch_to_rx()
        flags = radio.get_irq_flags()
        if flags.get("rx_done"):
            radio.clear_irq_flags()
            payload = radio.read_payload(nocheck=True)
            try:
                msg = decode_message(payload)
                if msg.get("type") == "HANDSHAKE_REQ":
                    sender = msg.get("from", "unknown")
                    print(f"[Handshake] Request received from {sender}")

                    reply = encode_message({
                        "type": "HANDSHAKE_ACK",
                        "from": hostname,
                        "ack_for": sender,
                        "timestamp": int(time.time())
                    })
                    self.switch_to_tx(reply)
                    time.sleep(0.5)
                    continue
            except Exception as e:
                print(f"[Handshake] Failed to decode packet: {e}")
        time.sleep(0.1)

@app.route('/api/discover', methods=['GET'])
def discover_endpoint(timeout=5):
        lora.switch_to_rx()
        start = time.time()
        while time.time() - start < timeout:
            flags = lora.radio.get_irq_flags()
            if flags.get("rx_done"):
                lora.radio.clear_irq_flags()
                payload = lora.radio.read_payload(nocheck=True)
                try:
                    msg = decode_message(payload)
                    if msg.get("from"):
                        print(f"[Discovery] Found endpoint: {msg['from']}")
                        return msg["from"]
                except:
                    pass
            time.sleep(0.05)
        return None

def beacon_response():
    """Respond to a beacon request with a simple message."""
    return encode_message({
        "type": "BEACON_RESPONSE",
        "from": socket.gethostname(),
        "timestamp": int(time.time())
    })

@app.route('/api/beacon', methods=['POST'])
def api_beacon():

    peer = discover_endpoint(timeout=5)
    if peer:
        message = {
            "type": "BEACON_MESSAGE",
            "from": socket.gethostname(),
            "to": peer,
            "timestamp": int(time.time())
        }
        payload = encode_message(message)
        lora.switch_to_tx(payload)
        return jsonify({"status": "message sent", "to": peer}), 200
    return jsonify({"error": "No endpoint discovered"}), 404
    
@app.route('/api/handshake', methods=['POST'])
def api_handshake():
    me = request.get_json().get("hostname", "node-A")
    peer = lora.initiate_handshake(my_hostname=me)
    if peer:
        return jsonify({"status": "connected", "peer": peer}), 200
    return jsonify({"error": "No handshake acknowledgment"}), 404

def handshake_listener():
    while True:
        lora.switch_to_rx()
        flags = radio.get_irq_flags()
        if flags.get("rx_done"):
            radio.clear_irq_flags()
            payload = radio.read_payload(nocheck=True)
            try:
                msg = decode_message(payload)
                if msg.get("type") == "HANDSHAKE_REQ":
                    sender = msg.get("from", "unknown")
                    print(f"[Handshake] Request received from {sender}")

                    reply = encode_message({
                        "type": "HANDSHAKE_ACK",
                        "from": socket.gethostname(),
                        "ack_for": sender,
                        "timestamp": int(time.time())
                    })
                    lora.switch_to_tx(reply)
                    time.sleep(0.5)
            except Exception as e:
                print(f"[Handshake] Decode error: {e}")
        time.sleep(0.1)
    
@app.route('/api/relay', methods=['POST'])
def api_relay():
    if not last_sent_msg:
        return jsonify({"error": "No message to relay"}), 404

    peer = lora.discover_endpoint(timeout=5)
    if not peer:
        return jsonify({"error": "No peer detected"}), 404

    lora.sync_to_peer(last_sent_msg)
    return jsonify({"status": "relayed", "to": peer}), 200


@app.route('/api/registers', methods=['GET'])
def api_registers():
    try:
        reg_map = {
            "version":       radio.get_register(0x42),
            "rssi":          radio.get_register(0x1A),
            "snr":           radio.get_register(0x1B),
            "irq_flags":     radio.get_register(0x12),
            "op_mode":       radio.get_register(0x01),
            "payload_length":radio.get_register(0x22)
        }
        return jsonify(reg_map), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/scan', methods=['GET'])
def api_scan():
    samples = []
    for _ in range(5):
        samples.append({
            "rssi": radio.get_rssi(),
            "snr":  radio.get_snr()
        })
        time.sleep(1)
    return jsonify(samples), 200

@app.route('/api/receive', methods=['GET'])
def api_receive():
    global last_sent_msg
    try:
        payload, meta = lora.listen_once(timeout=5)
        if not payload and last_sent_msg:
            return jsonify({
                "message": last_sent_msg,
                "quality": 100,
                "meta": {"source": "local-fallback"}
            }), 200

        if not payload:
            return jsonify({"error": "No message received"}), 404

        decoded = decode_message(payload)
        score   = crc_score(payload)
        return jsonify({
            "message": decoded,
            "quality": score,
            "meta": meta
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def api_status():
    status = lora.get_status()
    flags  = radio.get_irq_flags()
    hostname = "lora-node-001"  # or dynamically get from config/env

    if tx_queue.qsize() > 0 or flags.get("tx_done") == 0:
        server_state = "busy"
    elif flags.get("valid_header") or flags.get("rx_done"):
        last = radio.read_payload(nocheck=True)
        try:
            msg = decode_message(last)
            server_state = msg.get("from", hostname)
        except:
            server_state = hostname
    else:
        server_state = "offline"

    return jsonify({
        "rx_mode": status.get("rx_mode_active"),
        "tx_queue_depth": tx_queue.qsize(),
        "rssi": status.get("rssi"),
        "snr": status.get("snr"),
        "busy": False,
        "server_state": server_state
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
    return jsonify({"status": "ok"}), 200

def sync_loop():
    while True:
        if not sync_queue:
            time.sleep(1)
            continue

        item = sync_queue.pop(0)
        print(f"[SYNC] Processing message from {item['message']['from']}")

        peer = lora.discover_endpoint(timeout=5)
        if not peer:
            print("[SYNC] No peer found. Requeuing message.")
            sync_queue.append(item)
            time.sleep(2)
            continue

        lora.sync_to_peer(item["message"])
        item["status"] = "sent"
        synced_messages.append(item)
        time.sleep(0.5)


if __name__ == '__main__':
    print("Starting Dummy-LoRa backend API on port 5000!")
    threading.Thread(target=sync_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)

