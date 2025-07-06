from flask import Flask, jsonify, request, Response
import json, time
from message_store import MessageStore
from config import ADMIN_USERS
import socket

app = Flask(__name__)
store = MessageStore()

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({
        'pong': True,
        'server_time': time.time()
    })

@app.route('/api/pong', methods=['POST'])
def pong():
    data = request.get_json(silent=True) or {}
    client_time = data.get('client_time')
    server_time = time.time()
    latency = server_time - client_time if client_time else None
    print(f"[PONG] Client timestamp: {client_time}, Latency: {latency:.3f}s")
    return jsonify({
        'received': True,
        'server_time': server_time,
        'latency': latency
    })

@app.route('/api/inbox', methods=['GET'])
def get_inbox():
    return jsonify(store.all())

@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.get_json(silent=True) or request.form
    sender = data.get('from')
    text   = data.get('message')
    if not sender or not text:
        return jsonify({'error': 'need from & message'}), 400
    msg = store.add(sender, text)
    return jsonify(msg), 201

@app.route('/api/user/settings')
def user_settings():
    username = request.cookies.get('username', '').lower()
    is_admin = username in ADMIN_USERS
    return jsonify({
        'username': username,
        'is_admin': is_admin,
        'config_options': is_admin
            and {"max_log": 1000, "stream_debug": True}
            or {}
    })

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
    return load_config('config/lora_gateway.json')


@app.route('/config/info/lora-device')
def config_lora_device():
    return jsonify({
        'enabled': True,
        'device_id': 'LoRaDevice01',
        'firmware_version': '1.0.0'
    })

@app.route('/config/lora-device', methods=['POST'])
def config_lora_device_update():
    data = request.get_json(silent=True) or {}
    # Update the configuration with the new data
    return jsonify({'status': 'success'})

@app.route('/api/stream')
def message_stream():
    def event_stream():
        last_index = len(store.all())
        while True:
            all_msgs = store.all()
            # send any new messages
            for msg in all_msgs[last_index:]:
                payload = json.dumps(msg)
                yield f"event: message\ndata: {payload}\n\n"
            last_index = len(all_msgs)
            time.sleep(1)   # adjust interval as you like
    return Response(event_stream(),
                    mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache',
                             'X-Accel-Buffering':'no'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
