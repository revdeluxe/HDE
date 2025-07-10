from flask import Flask, jsonify, request, Response
import json, time, threading
from message_store import MessageStore
from lora_interface import LoRaSender, LoRaReceiver
from config import ADMIN_USERS
from SX127x.LoRa import LoRa, MODE

# 1) Instantiate your hardware LoRa radio with the correct signature
radio = LoRa(
    verbose=False,
    do_calibration=True,
    calibration_freq=868
)

# 2) Configure the radio
radio.set_mode(MODE.STDBY)
radio.set_freq(915e6)  
radio.set_pa_config(
    pa_select=1,      # PA_BOOST
    max_power=7,      # max current headroom
    output_power=15   # ~17 dBm
)

# 3) Wire that radio instance into your sender and receiver
sender   = LoRaSender(radio)
receiver = LoRaReceiver(radio)

app = Flask(__name__)
store   = MessageStore()

CHUNK_SIZE = 240
INTER_CHUNK_DELAY = 0.15  # seconds

def broadcast_checksum():
    crc = store.checksum()
    sender.send_lora({"type":"checksum","crc":crc})

def send_chunks():
    data = store.to_bytes()
    total = (len(data) + CHUNK_SIZE - 1)//CHUNK_SIZE
    for i in range(total):
        chunk = data[i*CHUNK_SIZE:(i+1)*CHUNK_SIZE]
        env = {"type":"chunk","idx":i,"total":total,"data":chunk.hex()}
        sender.send_lora(env)
        time.sleep(INTER_CHUNK_DELAY)

@app.route('/api/send', methods=['POST'])
<<<<<<< HEAD
def api_send():
    d = request.get_json() or {}
    sender_name = d.get("from")
    text        = d.get("message")
    if not sender_name or not text:
        return jsonify({"error":"need from & message"}),400

    msg = store.add(sender_name, text)
    sender.send_lora({"type":"message","msg":msg})
    broadcast_checksum()
    return jsonify(msg), 201

@app.route('/api/inbox')
def api_inbox():
    return jsonify(store.all())
=======
def send_message():
    data = request.get_json() or {}
    sender_name = data.get('from')
    text        = data.get('message')
    if not sender_name or not text:
        return jsonify({'error':'need from & message'}),400

    # 1) add to local store
    msg = store.add(sender_name, text)

    # 2) broadcast over LoRa with a "type" envelope
    payload = {"type":"message", "msg": msg}
    sender.send_lora(payload)

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
        return jsonify(receiver.get_status())
    except Exception as e:
        app.logger.exception("LoRa metrics failed")
        return jsonify({"error": str(e)}), 500

@app.route('/api/send_lora', methods=['POST'])
def send_over_lora():
    data = request.get_json(silent=True) or {}
    msg  = store.add(data['from'], data['message'])
    success = sender.send_lora(msg)
    return jsonify({'msg': msg, 'sent': success}), 201

@app.route('/api/receive_lora')
def receive_over_lora():
    msg, quality = receiver.listen_once(timeout=5)
    if not msg:
        return jsonify({'error': 'timeout'}), 504
    return jsonify({'msg': msg, 'stream_quality': quality})
>>>>>>> 55e9d30b4c2fbdb827eafa73b3464c7e7165ba40

@app.route('/api/stream')
def api_stream():
    def gen():
        last = len(store.all())
        syncing = False

        while True:
<<<<<<< HEAD
            pkt,_ = receiver.listen_once(timeout=0.1)
            if pkt:
                ptype = pkt.get("type")
                if ptype=="message":
                    m = pkt["msg"]
                    store.add(m["from"],m["message"],
                              msg_id=m["id"],ts=m["ts"],origin=m["origin"])
                    if m["origin"]!=store.self_id:
                        sender.send_lora({"type":"confirm","msg_id":m["id"],"to":m["origin"]})

                elif ptype=="confirm" and pkt.get("to")==store.self_id:
                    store.confirm(pkt["msg_id"])

                elif ptype=="checksum":
                    if pkt["crc"] != store.checksum():
                        syncing = True
                        yield "event: sync:start\ndata:{}\n\n"
                        send_chunks()
                        yield "event: sync:end\ndata:{}\n\n"
                    else:
                        sender.send_lora({"type":"ack_ok","to":pkt.get("from")})

                elif ptype=="chunk":
                    # reassemble chunks
                    # (store in temp dict, then write messages.json and reload store)
                    # emit progress via SSE if desired
                    pass

                elif ptype=="ack_ok":
                    # nothing to do sync not needed
                    pass

            # SSE push new messages
            all_msgs = store.all()
            for m in all_msgs[last:]:
                yield f"event: message\ndata:{json.dumps(m)}\n\n"
            last = len(all_msgs)

            # confirmations
            for m in all_msgs:
                if m["status"]=="confirmed" and not m.get("_acked"):
                    yield f"event: confirm\ndata:{m['id']}\n\n"
                    m["_acked"]=True

            # heartbeat
            yield "event: heartbeat\ndata:{{}}\n\n"
            time.sleep(1)
=======
            # 1) pull in any LoRa packets
            pkt, _ = receiver.listen_once(timeout=0.1)
            if pkt and pkt.get("type") == "message":
                msg = pkt["msg"]
                # merge into local store
                store.add(msg["from"], msg["message"], msg_id=msg["id"], ts=msg["ts"])

            # 2) emit new chat msgs via SSE
            all_msgs = store.all()
            for m in all_msgs[last_index:]:
                yield f"event: message\ndata: {json.dumps(m)}\n\n"
            last_index = len(all_msgs)

            # 3) heartbeat + link-stats
            stats = receiver.get_status()
            yield f"event: quality\ndata: {json.dumps(stats)}\n\n"

            time.sleep(1)
    return Response( event_stream(),
                     mimetype='text/event-stream',
                     headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'} )
>>>>>>> 55e9d30b4c2fbdb827eafa73b3464c7e7165ba40

    return Response(gen(),
                    mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)
