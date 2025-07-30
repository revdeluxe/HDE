# main_flask.py

from flask import Flask, jsonify, request, send_from_directory, abort
from pathlib import Path
import json
import time
import os

from parser import Parser
from stream import MessageStream
from pyLoRa.configure import run_checks
from pyLoRa.lora_module import LoRa
lora = LoRa()
# Initialize Flask and LoRa
app = Flask(__name__)

lora.reset()
lora.set_frequency(433)
lora.set_tx_power(14)

messages_dir = Path("messages")
messages_file = messages_dir / "messages.json"
to_send_file = messages_dir / "to_send.json"
stream = MessageStream(timeout=120)
checksum = Parser.updated_messages_checksum(messages_file)
from_user = Parser.parse_username(checksum)

def send_via_lora(message: str):
    result = lora.send(message)
    if not result:
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    return jsonify({"status": "ok"})

def auto_save_message(data: dict):
    messages_dir.mkdir(parents=True, exist_ok=True)

    if not messages_file.exists():
        messages_file.write_text("[]")

    with open(messages_file, "r+") as f:
        messages = json.load(f)
        messages.append({
            "sender": data.get("sender"),
            "message": data.get("message"),
            "timestamp": time.time()
        })
        f.seek(0)
        json.dump(messages, f)
        f.truncate()

@app.route("/api/working_directory")
def get_working_directory():
    return jsonify({"cwd": os.getcwd()})

@app.route("/service-offline.html")
def service_offline():
    return send_from_directory("../html", "service-offline.html")

@app.route("/")
def index():
    return send_from_directory("../html", "index.html")

@app.route("/api/send/<message>", methods=["POST"])
def send_message(message):
    if not message:
        abort(400, description="Message content is required")

    result = send_via_lora(message)
    return result

@app.route("/api/messages")
def get_messages():
    return jsonify({"data": MessageStream.load_messages(messages_file)})

@app.route("/api/checksum")
def get_checksum():
    return jsonify({"checksum": checksum})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
