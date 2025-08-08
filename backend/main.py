# main_flask.py

from flask import Flask, jsonify, request, send_from_directory, abort
from pathlib import Path
import json
import time
import os
import atexit
import aiofiles
import asyncio
from lora_engine import LoRaEngine
from parser import Parser
from stream import MessageStream
from threading import Lock
# Initialize Flask and LoRa
app = Flask(__name__)
file_lock = Lock()
stream = MessageStream()
messages_dir = Path("messages")
messages_file = messages_dir / "messages.json"
to_send_file = messages_dir / "to_send.json"
save_dir = Path("messages/saves")
checksum = Parser.updated_messages_checksum(messages_file)
from_user = Parser.parse_username(checksum)
lora_engine = LoRaEngine()
lora_engine.get_state()
lora_engine.set_state("idle")

def parse_heard_data(data: str):
    """
    Parses the received LoRa data and returns a structured dictionary.
    """
    parsed = Parser.parse_message(data)
    if not parsed["valid"]:
        return None

    chunk_data = parsed["fields"].get("chunk")
    if Parser.is_it_in_batches(parsed):
        Parser.reassemble_chunks(parsed["fields"])
        chunk_id, chunk_message = extract_chunk_info(chunk_data)
    else:
        # fallback to flat message
        chunk_id, chunk_message = (1, parsed["fields"].get("message", ""))

    return {
        "sender": parsed["fields"].get("from"),
        "timestamp": int(parsed["fields"].get("timestamp", time.time())),
        "chunk_batch": parsed["fields"].get("batch", 0),
        "chunk_id": chunk_id,
        "chunk_message": chunk_message
    }


def extract_chunk_info(chunks):
    if not chunks or len(chunks) == 0:
        return (0, "")
    return (chunks[0].get("id", 0), chunks[0].get("message", ""))


def parse_send_data(data: dict):
    """
    Parses the data to be sent via LoRa and returns a structured dictionary.
    """
    print(f"[DEBUG] Parsing send data: {data}")
    if not isinstance(data, dict):
        print("[ERROR] Invalid data format, expected a dictionary.")
        return data
    parsed = Parser.parse_message(data)
    if not parsed["valid"]:
        return None

    chunk_data = parsed["fields"].get("chunk")
    chunk_id, chunk_message = extract_chunk_info(chunk_data)

    return {
        "from": parsed["fields"].get("from"),
        "checksum": parsed["fields"].get("checksum"),
        "timestamp": int(parsed["fields"].get("timestamp", time.time())),
        "chunk_batch": parsed["fields"].get("batch", 0),
        "chunk_id": chunk_id,
        "chunk_message": chunk_message
    }
    
def save_message_manually(entry):
    filepath = "messages/messages.json"  # match the reader path
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[DEBUG] Appended new message to {filepath}")
    except Exception as e:
        print(f"[ERROR] Saving message failed: {e}")




def auto_save_message_async(data: dict):
    messages_dir.mkdir(parents=True, exist_ok=True)

    if not messages_file.exists():
        messages_file.write_text("[]")  # Optional: make this async too

    mdata = Parser.prepare(data)

    with open(messages_file, "r+") as f:
        content = f.read()
        try:
            messages = json.loads(content)
        except json.JSONDecodeError:
            messages = []
        messages.append(mdata)

        f.seek(0)
        f.write(json.dumps(messages))
        f.truncate()

@app.route("/api/working_directory")
def get_working_directory():
    return jsonify({"cwd": os.getcwd()})

@app.route("/api/send", methods=["POST"])
def send_message():
    lora_engine.get_state()
    data = request.get_json()
    from_field = data.get("from")
    message = data.get("message")
    checksum = data.get("checksum")

    if not from_field or not message or not checksum:
        return jsonify({"error": "Missing fields"}), 400

    # Structure the new message
    new_entry = {
        "from": from_field,
        "timestamp": int(time.time()),
        "chunk_batch": Parser.generate_batch_id(),
        "chunk": [
            {
                "id": Parser.generate_chunk_id(),
                "message": message
            }
        ]
    }
    print(f"[DEBUG] New entry to send: {new_entry}")
    lora_engine.queue_message(new_entry)
    # Manually save the message to a log (append style)
    print(f"[DEBUG] Saving message: {new_entry}")
    save_message_manually(new_entry)

    # Simulate LoRa send (or place real send function here)
    print(f"[INFO] Sending via LoRa: {message}")

    return jsonify({"status": "success", "sent": new_entry}), 200



@app.route("/api/messages/<filename>", methods=["GET"])
def source_messages(filename):
    path = os.path.join("messages", filename)
    if not os.path.exists(path):
        return jsonify({"data": []}), 200

    print(f"[DEBUG] Reading messages from {path}")
    if not os.path.isfile(path):
        return jsonify({"error": "File not found"}), 404
    
    async def read():
        async with aiofiles.open(path, mode='r') as f:
            lines = await f.readlines()
            return [json.loads(line.strip()) for line in lines if line.strip()]

    lora_state = lora_engine.get_state()
    print(f"[DEBUG] LoRa state: {lora_state}")
    messages = asyncio.run(read())
    print(f"[DEBUG] Messages read: {len(messages)} entries")
    return jsonify({"lora": lora_state,"data": messages})

@app.route("/api/state", methods=["GET"])
def get_state():
    return jsonify({"state": lora_engine.get_state()})

@app.route("/api/checksum")
def get_checksum():
    return jsonify({"checksum": checksum})

def cleanup_gpio():
        lora_engine.shutdown()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    atexit.register(cleanup_gpio)

