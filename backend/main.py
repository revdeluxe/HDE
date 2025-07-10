from flask import Flask, jsonify, request, Response
import time, json, socket, utils
from SX127x.board_config import BOARD
from lora_interface import LoRaSender, LoRaReceiver
from message_store import MessageStore
from config import ADMIN_USERS

app = Flask(__name__)
store = MessageStore()

# ── LoRa Initialization ───────────────────────────────────────────
BOARD.setup()
lora = LoRaSender()
lora.set_freq(434.0)
lora.set_spreading_factor(7)
lora.set_pa_config(pa_select=1)

# ── API Endpoints ─────────────────────────────────────────────────

@app.route('/api/ping')
def ping():
    return jsonify({'pong': True, 'server_time': time.time()})

@app.route('/api/pong', methods=['POST'])
def pong():
    data = request.get_json(silent=True) or {}
    client_time = data.get('client_time')
    server_time = time.time()
    latency = server_time - client_time if client_time else None
    print(f"[PONG] Client timestamp: {client_time}, Latency: {latency:.3f}s")
    return jsonify({'received': True, 'server_time': server_time, 'latency': latency})

@app.route('/api/inbox')
def get_inbox():
    return jsonify(store.all())

@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.get_json(silent=True) or request.form
    sender = data.get('from')
    text = data.get('message')
    if not sender or not text:
        return jsonify({'error': 'need from & message'}), 400
    msg = store.add(sender, text)
    return jsonify(msg), 201

@app.route('/api/user/settings')
def user_settings():
    username = request.cookies.get('username', '').lower()
    is_admin = username in ADMIN_USERS
    config_options = {"max_log": 1000, "stream_debug": True} if is_admin else {}
    return jsonify({'username': username, 'is_admin': is_admin, 'config_options': config_options})

@app.route('/api/lora_metrics')
def lora_metrics():
    try:
        r = LoRaReceiver()
        r.set_freq(434.0)
        r.set_spreading_factor(7)
        r.set_pa_config(pa_select=1)
        return jsonify(r.get_status())
    except Exception as e:
        app.logger.exception("LoRa metrics failed")
        return jsonify({"error": str(e)}), 500


@app.route('/api/send_lora', methods=['POST'])
def send_over_lora():
    data = request.get_json(silent=True) or {}
    if not data.get('from') or not data.get('message'):
        return jsonify({'error': 'need from & message'}), 400
    msg = store.add(data['from'], data['message'])
    success = lora.send_lora(msg)
    return jsonify({'msg': msg, 'sent': success}), 201

@app.route('/api/receive_lora')
def receive_over_lora():
    receiver = LoRaReceiver()
    receiver.set_freq(434.0)
    receiver.set_spreading_factor(7)
    receiver.set_pa_config(pa_select=1)
    msg, quality = receiver.listen_once(timeout=5)
    if not msg:
        return jsonify({'error': 'timeout'}), 504
    return jsonify({'msg': msg, 'stream_quality': quality})

@app.route('/api/stream')
def message_stream():
    def event_stream():
        last_index = len(store.all())
        while True:
            all_msgs = store.all()
            for msg in all_msgs[last_index:]:
                yield f"event: message\ndata: {json.dumps(msg)}\n\n"
            last_index = len(all_msgs)

            # send a heartbeat every second
            yield "event: heartbeat\ndata: {}\n\n"
            time.sleep(1)
    return Response(event_stream(),
                    mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

# ── Config Endpoints ──────────────────────────────────────────────

@app.route('/config/info', strict_slashes=False)
def config_info():
    return jsonify({
        'hostname': socket.gethostname(),
        'stream_quality': 'high',
        'firmware_version': '1.0.0'
    })

def load_config(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

@app.route('/config/info/general')
def config_info_general():
    return jsonify(load_config('config/general.json'))

@app.route('/config/info/lora-gateway')
def config_lora_gateway_info():
    return jsonify(load_config('config/lora_gateway.json'))

@app.route('/config/info/lora-device')
def config_lora_device():
    return jsonify({'enabled': True, 'device_id': 'LoRaDevice01', 'firmware_version': '1.0.0'})

@app.route('/config/lora-device', methods=['POST'])
def config_lora_device_update():
    data = request.get_json(silent=True) or {}
    # Perform update logic here
    return jsonify({'status': 'success'})

# ── App Entry Point ───────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
