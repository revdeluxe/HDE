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


@app.before_first_request
def begin_lora_rx():
    lora_engine.get_state()  # Ensure LoRa is initialized
    lora_engine.set_state("receive")  # Start in receive mode

@app.route("/api/send", methods=["POST"])
def send_lora():
    message = request.json.get("message", "")
    if message:
        lora_engine.queue_message(message)
        return jsonify({"status": "ok", "queued": message})
    return jsonify({"error": "No message"}), 400

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

async def auto_save_message_async(data: dict):
    messages_dir.mkdir(parents=True, exist_ok=True)

    if not messages_file.exists():
        messages_file.write_text("[]")  # Optional: make this async too

    mdata = Parser.prepare(data)

    async with aiofiles.open(messages_file, "r+") as f:
        content = await f.read()
        try:
            messages = json.loads(content)
        except json.JSONDecodeError:
            messages = []
        messages.append(mdata)

        await f.seek(0)
        await f.write(json.dumps(messages))
        await f.truncate()

@app.route("/api/working_directory")
def get_working_directory():
    return jsonify({"cwd": os.getcwd()})

@app.route("/api/send", methods=["POST"])
def send_message():
    try:
        from_field = request.json.get("from")
        raw_message = request.json.get("message")
        checksum = request.json.get("checksum")  # Optional: for verification

        if not raw_message:
            return jsonify({"status": "error", "error": "No message provided."}), 400
        if not from_field:
            return jsonify({"status": "error", "error": "No sender provided."}), 400

        # Parse and validate message (already includes CRC check)
        parsed = Parser.parse_message(raw_message)

        if not parsed["valid"]:
            return jsonify({"status": "error", "error": parsed.get("error", "Invalid message")}), 400

        # Replace 'from' field with client-supplied one (optional)
        parsed["from"] = from_field

        formatted = {
            "from": parsed["from"],
            "timestamp": parsed["timestamp"],
            "chunk_batch": parsed["batch"],
            "chunk": parsed["chunk"]
        }

        # Save to storage/messages.json
        try:
            if not os.path.exists("storage"):
                os.makedirs("storage")

            storage_path = "storage/messages.json"

            if os.path.exists(storage_path):
                with open(storage_path, "r") as f:
                    existing = json.load(f)
            else:
                existing = []

            existing.append(formatted)

            with open(storage_path, "w") as f:
                json.dump(existing, f, indent=2)

        except Exception as e:
            return jsonify({"status": "error", "error": f"Failed to save message: {e}"}), 500

        return jsonify({"status": "ok", "data": formatted}), 200

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500



@app.route("/api/messages", methods=["GET"])
def get_messages():
    # This should return recent messages from storage/logs
    messages = stream.load_messages()  # Your function here
    return jsonify({"data": messages})

@app.route("/api/messages/<filename>", methods=["GET"])
def source_messages(filename):
    path = os.path.join("messages", filename)
    if not os.path.exists(path):
        return jsonify({"data": []}), 200

    async def read():
        async with aiofiles.open(path, mode='r') as f:
            lines = await f.readlines()
            return [json.loads(line.strip()) for line in lines if line.strip()]

    messages = asyncio.run(read())
    return jsonify({"data": messages})

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

