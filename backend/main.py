# main.py

import json
import time
import socket
import queue
import threading

from threading import Lock
from flask import Flask, request, jsonify

from interface import LoRaInterface, chunk_payload
from utils import encode_message, decode_message, crc_score

app = Flask(__name__)

# —— Queues, Locks, Storage —— #
tx_queue      = queue.Queue()
sync_queue    = []
sync_lock     = Lock()
synced_messages = []
last_sent_msg = None

# —— Radio Setup —— #
# BOARD.setup() and BOARD.SpiDev() live inside interface.radio_init()
# LoRaInterface() will call radio_init() automatically
lora = LoRaInterface()

# —— Background Workers —— #

def tx_worker():
    """Pull chunks off tx_queue and send them."""
    while True:
        chunk = tx_queue.get()
        try:
            lora.switch_to_tx(chunk)
        except Exception as e:
            print("[TX Worker] Error sending:", e)
        finally:
            time.sleep(0.1)

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

@app.route('/api/send', methods=['POST'])
def api_send():
    global last_sent_msg
    data = request.get_json() or {}
    if 'from' not in data or 'message' not in data:
        return jsonify({"error": "Missing 'from' or 'message'"}), 400

    msg     = {
        'from':      data['from'],
        'message':   data['message'],
        'timestamp': data.get('timestamp', int(time.time()))
    }
    payload = encode_message(msg)

    # split & queue
    for chunk in chunk_payload(payload):
        tx_queue.put(chunk)

    last_sent_msg = msg
    # immediate local echo
    synced_messages.append({**msg, "source": "local", "status": "synced"})
    return jsonify({"status": "queued", "bytes": len(payload)}), 202

@app.route('/api/messages/<source>', methods=['GET'])
def api_messages_by_source(source):
    filtered = [m for m in synced_messages if m.get("source")==source]
    return jsonify(filtered[-50:]), 200

@app.route('/api/receive', methods=['GET'])
def api_receive():
    """Attempt one receive, fallback to last_sent_msg if none."""
    try:
        idx, raw, meta = lora.listen_once()
        if not raw and last_sent_msg:
            return jsonify({
                "message": last_sent_msg,
                "quality": 100,
                "meta":    {"source": "local-fallback"}
            }), 200

        if not raw:
            return jsonify({"error": "No message received"}), 404

        decoded = decode_message(raw)
        score   = crc_score(raw)
        return jsonify({
            "message": decoded,
            "quality": score,
            "meta":    meta
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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


if __name__ == '__main__':
    print("Starting LoRa Flask API on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
