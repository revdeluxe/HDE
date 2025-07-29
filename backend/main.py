# main.py

from fastapi import FastAPI, HTTPException, Request, Response, Cookie
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path
import json
import time

from parser import Parser
from stream import MessageStream

from pyLoRa.configure import run_checks
from pyLoRa.lora_handler import LoRaGPIOHandler
from pyLoRa.lora_module import LoRa

# Perform startup checks
run_checks()

# Initialize LoRa handler
gpio_handler = LoRaGPIOHandler()
gpio_handler.setup_gpio()

lora = LoRa(gpio_handler)
app = FastAPI()
messages_dir = Path("messages")
messages_file = messages_dir / "messages.json"
to_send_file = messages_dir / "to_send.json"
stream = MessageStream(timeout=120)  # 2-minute timeout for chunked messages

# Ensure messages/ folder and JSON files exist
messages_dir.mkdir(parents=True, exist_ok=True)
if not messages_file.exists():
    messages_file.write_text("[]")
if not to_send_file.exists():
    to_send_file.write_text("[]")

class RawMessage(BaseModel):
    data: str

class OutgoingMessage(BaseModel):
    to: str
    message: str
    timestamp: float | None = None

@app.post("/api/receive")
async def receive_message(raw: RawMessage):
    parsed = Parser.parse_message(raw.data)

    if not parsed["valid"]:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": parsed["error"]}
        )

    fields = parsed["fields"]
    reassembled = stream.add_chunk(
        sender=fields["from"],
        chunk_id=fields["chunk_id"],
        chunk_batch=fields["chunk_batch"],
        message=fields["message"],
        timestamp=fields["timestamp"]
    )

    if reassembled:
        entry = {
            "from": fields["from"],
            "message": reassembled,
            "chunk_batch": fields["chunk_batch"],
            "timestamp": fields["timestamp"],
            "timestamp_human": fields["timestamp_human"]
        }

        messages = json.loads(messages_file.read_text())
        messages.append(entry)
        messages_file.write_text(json.dumps(messages, indent=2))

        return {"status": "success", "stored": entry}

    return {"status": "pending", "message": "Chunk received, waiting for more."}

@app.post("/api/send")
async def send_message(payload: OutgoingMessage, username: str = Cookie(default="unknown")):
    entry = {
        "from": username,
        "to": payload.to,
        "message": payload.message,
        "timestamp": payload.timestamp or time.time()
    }

    queue = json.loads(to_send_file.read_text())
    queue.append(entry)
    to_send_file.write_text(json.dumps(queue, indent=2))

    # Transmit using LoRa
    data = f"{entry['from']}:{entry['to']}:{entry['message']}".encode('utf-8')
    lora.send(data)

    return {"status": "queued", "entry": entry}

@app.get("/api/messages")
async def get_messages():
    try:
        data = json.loads(messages_file.read_text())
        return {"status": "ok", "messages": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/messages/{source}")
async def get_file_messages(source: str):
    path = messages_dir / source
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)

@app.get("/api/messages/crc")
async def get_crc():
    from parser import file_crc32  # Import here to avoid circular issues
    return {
        "crc32": file_crc32(messages_file),
        "file": str(messages_file)
    }

@app.get("/api/messages/refresh")
async def refresh_messages():
    stream.cleanup()
    return {"status": "success", "message": "Old chunks cleaned up."}

@app.on_event("startup")
async def on_start():
    print("[🔌] API service started on port 5000")

@app.middleware("http")
async def cleanup_old_chunks(request: Request, call_next):
    stream.cleanup()
    return await call_next(request)

# To run this app on port 5000 with uvicorn:
# uvicorn main:app --host 0.0.0.0 --port 5000

if __name__ == "__main__":
    import asyncio
    from uvicorn import Config, Server

    async def start_server():
        config = Config(app=app, host="0.0.0.0", port=5000, log_level="info", reload=False)
        server = Server(config)
        await server.serve()

    asyncio.run(start_server())

