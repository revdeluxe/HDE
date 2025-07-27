# main.py
import os
import json
import time
import socket
import queue
import threading
import logging

from threading import Lock
from flask import Flask, request, jsonify, abort
from werkzeug.utils import secure_filename
from message_store import MessageStore
from interface import LoRaInterface, chunk_payload
from utils import encode_message, decode_message, crc_score
from threading import Lock

sync_lock = Lock()

# How long to wait for a peer ACK (seconds)
ACK_TIMEOUT = 2
app = Flask(__name__)

# —— Queues, Locks, Storage —— #
logging.basicConfig(level=logging.INFO)
tx_queue      = queue.Queue()
sync_queue    = []
sync_lock     = Lock()
synced_messages = []
last_sent_msg = None
store = MessageStore()

# —— Radio Setup —— #
# BOARD.setup() and BOARD.SpiDev() live inside interface.radio_init()
# LoRaInterface() will call radio_init() automatically
lora = LoRaInterface()

# —— Background Workers —— #
MESSAGE_DIR = './messages/'

@app.route('/api/messages/<source>', methods=['GET'])
def api_messages_from_file(source):
    """
    Treat <source> as the filename (without path traversal).
    E.g. GET /api/messages/message.json will load message.json
    from MESSAGE_DIR.
    """
    # Prevent path traversal attacks
    filename = secure_filename(source)
    # Ensure the extension is .json
    if not filename.lower().endswith('.json'):
        filename += '.json'

    full_path = os.path.join(MESSAGE_DIR, filename)

    # Check that the file actually exists under MESSAGE_DIR
    if not os.path.isfile(full_path):
        abort(404, description=f"File {filename} not found")

    # Load and return its contents
    with open(full_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            abort(500, description=f"Invalid JSON in {filename}")

    return jsonify(data), 200

@app.route('/api/messages/', methods=['GET'])
def api_list_sources():
    files = [f for f in os.listdir(MESSAGE_DIR)
             if f.lower().endswith('.json')]
    return jsonify(files), 200


def tx_worker():
    """Continuously sends chunks from tx_queue over LoRa."""
    while True:
        chunk = tx_queue.get()  # blocks until a chunk is available
        try:
            lora.send(chunk)
            logging.info(f"TX → sent chunk of {len(chunk)} bytes")
        except Exception as e:
            logging.error(f"TX error: {e}")
        finally:
            tx_queue.task_done()
        # throttle if needed
        time.sleep(0.05)

# Start the TX thread as a daemon so it exits with the main process
threading.Thread(target=tx_worker, daemon=True).start()

def sync_loop():
    """Process sync_queue: discover peer, then sync_to_peer."""
    while True:
        sync_lock.acquire()
        if sync_queue:
            item = sync_queue.pop(0)
            peer = lora.discover_endpoint(timeout=5)
            if peer:
                lora.sync_to_peer(item["message"])
                item["status"] = "sent"
                synced_messages.append(item)
            else:
                # no peer found—requeue and try later
                sync_queue.append(item)
        sync_lock.release()
        time.sleep(1)

def handshake_listener():
    """Always-on listener for incoming HANDSHAKE_REQ."""
    while True:
        idx, raw, _ = lora.listen_once()
        if raw:
            try:
                msg = decode_message(raw)
                if msg.get("type") == "HANDSHAKE_REQ":
                    sender = msg.get("from", "unknown")
                    print(f"[Handshake] Req from {sender}")
                    reply = encode_message({
                        "type": "HANDSHAKE_ACK",
                        "from": socket.gethostname(),
                        "ack_for": sender,
                        "timestamp": int(time.time())
                    })
                    lora.switch_to_tx(reply)
            except Exception as e:
                print("[Handshake] decode error:", e)
        time.sleep(0.1)

# Start threads
threading.Thread(target=tx_worker,       daemon=True).start()
threading.Thread(target=sync_loop,       daemon=True).start()
threading.Thread(target=handshake_listener, daemon=True).start()

# —— Flask Hooks & Endpoints —— #

@app.before_first_request
def boot_beacon():
    """Send a BOOT_OK on startup."""
    beacon = encode_message({
        "type":      "BOOT_OK",
        "message": "LoRa service started",
        "from":      socket.gethostname(),
        "timestamp": int(time.time())
    })
    tx_queue.put(beacon)

@app.route("/api/send", methods=["POST"])
def api_send():
    global last_sent_msg

    data = request.get_json() or {}
    if "from" not in data or "message" not in data:
        return jsonify({"error": "Missing 'from' or 'message'"}), 400

    # 1. Persist locally as "pending"
    msg = store.add(
        sender=data["from"],
        text=data["message"],
        ts=data.get("timestamp"),
    )
    last_sent_msg = msg

    # 2. Encode, chunk, and enqueue for TX
    payload = encode_message(msg)
    for chunk in chunk_payload(payload):
        tx_queue.put(chunk)

    logging.info(f"Queued {len(payload)} bytes in {tx_queue.qsize()} chunks")
    return jsonify({"status": "queued", "id": msg["id"], "bytes": len(payload)}), 202


@app.route("/api/messages/<source>", methods=["GET"])
def api_messages_by_source(source):
    """Return up to 50 messages filtered by 'origin' (local vs remote)."""
    all_msgs = store.all()
    filtered = [m for m in all_msgs if m.get("origin") == source]
    # Return the most recent 50
    return jsonify(filtered[-50:]), 200


@app.route("/api/receive", methods=["GET"])
def api_receive():
    """Try one LoRa receive; fallback to last_sent_msg if nothing on-air."""
    try:
        seq, raw_bytes, meta = lora.listen_once()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # No packet received → fallback or 404
    if not raw_bytes:
        if last_sent_msg:
            return jsonify({
                "message": last_sent_msg,
                "quality": 100,
                "meta":    {"source": "local-fallback"}
            }), 200

        return jsonify({"error": "No message received"}), 404

    # Decode and compute quality score
    decoded = decode_message(raw_bytes)
    score   = crc_score(raw_bytes)

    # Persist under "received" status
    store.add(
        sender=decoded["from"],
        text=decoded["message"],
        msg_id=decoded["id"],
        ts=decoded.get("timestamp"),
        origin=socket.gethostname()
    )

    return jsonify({
        "message": decoded,
        "quality": score,
        "meta":    meta
    }), 200

@app.route('/api/handshake', methods=['POST'])
def api_handshake():
    me   = request.get_json().get("hostname", socket.gethostname())
    peer = lora.initiate_handshake(my_hostname=me)
    if peer:
        return jsonify({"status": "connected", "peer": peer}), 200
    return jsonify({"error": "No handshake ACK"}), 404

@app.route('/api/discover', methods=['GET'])
def api_discover():
    peer = lora.discover_endpoint(timeout=5)
    if peer:
        return jsonify({"peer": peer}), 200
    return jsonify({"error": "No endpoint found"}), 404

@app.route('/api/beacon', methods=['POST'])
def api_beacon():
    peer = lora.discover_endpoint(timeout=5)
    if peer:
        msg = encode_message({
            "type":      "BEACON_MESSAGE",
            "from":      socket.gethostname(),
            "to":        peer,
            "timestamp": int(time.time())
        })
        tx_queue.put(msg)
        return jsonify({"status": "sent", "to": peer}), 200
    return jsonify({"error": "No peer found"}), 404

@app.route('/api/relay', methods=['POST'])
def api_relay():
    if not last_sent_msg:
        return jsonify({"error": "Nothing to relay"}), 404

    peer = lora.discover_endpoint(timeout=5)
    if not peer:
        return jsonify({"error": "No peer detected"}), 404

    sync_lock.acquire()
    sync_queue.append({"message": last_sent_msg, "source": "relay", "status": "pending"})
    sync_lock.release()

    return jsonify({"status": "queued for relay", "to": peer}), 200

@app.route('/api/registers', methods=['GET'])
def api_registers():
    try:
        regs = {
            "version":        lora.radio.get_register(0x42),
            "rssi_raw":       lora.radio.get_register(0x1A),
            "snr_raw":        lora.radio.get_register(0x1B),
            "irq_flags":      lora.radio.get_register(0x12),
            "op_mode":        lora.radio.get_register(0x01),
            "payload_length": lora.radio.get_register(0x22),
        }
        return jsonify(regs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/scan', methods=['GET'])
def api_scan():
    samples = []
    for _ in range(5):
        samples.append({
            "rssi": lora.get_rssi(),
            "snr":  lora.get_snr()
        })
        time.sleep(1)
    return jsonify(samples), 200

@app.route('/api/status', methods=['GET'])
def api_status():
    status     = lora.get_status()
    flags      = lora.get_irq_flags()
    busy_tx    = (tx_queue.qsize() > 0 or flags.get("tx_done")==0)
    valid_rx   = flags.get("valid_header") or flags.get("rx_done")
    server_st  = socket.gethostname() if not valid_rx else "receiving"

    return jsonify({
        "rx_mode":       status["rx_mode_active"],
        "tx_queue_depth": tx_queue.qsize(),
        "rssi":          status["rssi"],
        "snr":           status["snr"],
        "busy":          busy_tx,
        "server_state":  server_st
    }), 200

@app.route('/api/broadcast', methods=['POST'])
def api_broadcast():
    data = request.get_json() or {}
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    payload = json.dumps(data).encode()
    tx_queue.put(payload)
    return jsonify({"status": "broadcast queued"}), 202

@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({"status": "ok"}), 200

@app.route('/api/sync', methods=['POST'])
def api_sync():
    """Send all pending messages, wait for peer ACKs, and confirm locally."""
    with sync_lock:
        # 1. Gather all pending messages from the store
        pending = [m for m in store.all() if m["status"] == "pending"]
        if not pending:
            return jsonify({"status": "no pending messages"}), 200

        results = []
        for msg in pending:
            # 2. Encode + enqueue for TX
            payload = encode_message(msg)
            for chunk in chunk_payload(payload):
                tx_queue.put(chunk)

            # 3. Optionally wait for an ACK from peer
            start = time.time()
            acked = False
            while time.time() - start < ACK_TIMEOUT:
                seq, raw, meta = lora.listen_once()
                if raw:
                    dec = decode_message(raw)
                    if dec.get("type") == "ACK" and dec.get("id") == msg["id"]:
                        acked = True
                        break
                time.sleep(0.1)

            # 4. Update store based on ACK result
            status = "synced" if acked else "failed"
            if acked:
                store.confirm(msg["id"])
            results.append({"id": msg["id"], "status": status})

        return jsonify({
            "status":        "sync completed",
            "results":       results,
            "synced_count":  sum(1 for r in results if r["status"]=="synced"),
            "failed_count":  sum(1 for r in results if r["status"]=="failed")
        }), 200


if __name__ == '__main__':
    logging.info("Starting LoRa Flask API on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
