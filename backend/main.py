# main_flask.py

from flask import Flask, jsonify, request, send_from_directory, abort
from pathlib import Path
import json
import time
import os
import atexit
import aiofiles
import asyncio
from threading import Thread
import threading
from listener_thread import listen_lora_forever
from parser import Parser
from stream import MessageStream
from pyLoRa.configure import run_checks
from pyLoRa.lora_module import LoRa
from threading import Lock
lora = LoRa()
# Initialize Flask and LoRa
app = Flask(__name__)
file_lock = Lock()
lora.reset()
lora.set_frequency(433)
lora.set_tx_power(14)
stream = MessageStream()
messages_dir = Path("messages")
messages_file = messages_dir / "messages.json"
to_send_file = messages_dir / "to_send.json"
save_dir = Path("messages/saves")
checksum = Parser.updated_messages_checksum(messages_file)
from_user = Parser.parse_username(checksum)

@app.before_first_request
def start_lora_listener():
    t = threading.Thread(target=listen_lora_forever, daemon=True)
    t.start()

def send_via_lora(message: str):
    batch_id = Parser.generate_batch_id(to_send_file)
    chunk_id = Parser.generate_chunk_id(to_send_file)
    timestamp = int(time.time())

    # Prepare single or multiple chunks
    chunks = Parser.split_into_chunks(message) if Parser.should_it_be_in_batches(message) else [message]

    prepared_data = {
        "from": from_user,
        "timestamp": timestamp,
        "batch": batch_id,
        "chunk": []
    }

    for i, c in enumerate(chunks, start=1):
        prepared_data["chunk"].append({
            "id": i,
            "message": c
        })

    encoded_message = Parser.prepare(prepared_data)

    # Send each chunked message (could also send full JSON if small enough)
    lora.set_mode_tx()
    if isinstance(encoded_message, list):
        for msg in encoded_message:
            lora.send(msg)
    else:
        lora.send(encoded_message)

    return jsonify({"status": "ok"})


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


def parse_send_data(data: str):
    """
    Parses the data to be sent via LoRa and returns a structured dictionary.
    """
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

def get_lora_state():
    """
    Returns the current LoRa state.
    """ 
    return {
        "mode": lora.get_mode(),
        "frequency": lora.get_frequency(),
        "tx_power": lora.get_tx_power(),
        "rssi": lora.get_rssi(),
        "snr": lora.get_snr()
    }

@app.route("/api/working_directory")
def get_working_directory():
    return jsonify({"cwd": os.getcwd()})

@app.route("/api/send", methods=["POST"])
def send_message():
    try:
        data = request.json
        from_user = data.get("from", "unknown")
        raw_message = data.get("message", "").strip()
        print(f"[DEBUG] Received message from {from_user}: {raw_message}")
        if not raw_message:
            return jsonify({"status": "error", "message": "No message provided"}), 400

        timestamp = int(time.time())
        batch_id = 1  # Increment or generate uniquely if needed

        # Chunk message if needed (you can define chunk_message())
        chunks = Parser.chunk_message(raw_message)  # Returns a list of {id, text}

        for i, chunk in enumerate(chunks, start=1):
            formatted = f"from={from_user};timestamp={timestamp};chunk_batch={batch_id};chunk_id={i};message={chunk['text']};"
            print(f"[DEBUG] Sending chunk: {formatted}")
            lora.send(formatted.encode("utf-8"))
            Parser.save_chunk_data(from_user, timestamp, batch_id, i, chunk['text'])

        # Attempt reassembly
        if len(chunks) == 1:
            final_message = raw_message
        else:
            final_message = Parser.reassemble_chunks(from_user, timestamp, batch_id)

        checksum = Parser.calculate_crc(final_message)
        print(f"[INFO] Message sent. CRC: {checksum}")

        return jsonify({
            "status": "ok",
            "message": final_message,
            "checksum": checksum
        }), 200

    except Exception as e:
        print(f"[ERROR] Send failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



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



@app.route("/api/checksum")
def get_checksum():
    return jsonify({"checksum": checksum})

def cleanup_gpio():
        if hasattr(lora, "gpio"):
            lora.gpio.cleanup()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    atexit.register(cleanup_gpio)

