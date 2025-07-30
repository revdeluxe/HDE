# main.py

from unittest import result
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

# Initialize LoRa handler
lora = LoRa()
app = FastAPI()
lora.reset()
lora.set_frequency(433)
lora.set_tx_power(14)
messages_dir = Path("messages")
messages_file = messages_dir / "messages.json"
to_send_file = messages_dir / "to_send.json"
stream = MessageStream(timeout=120)  # 2-minute timeout for chunked messages
checksum = Parser.updated_messages_checksum(messages_file)
from_user = Parser.parse_username(checksum)

async def send_via_lora(message: str):
    result = await lora.send_message(message)
    if not result:
        return JSONResponse(status_code=500, content={"status": "error", "message": "Failed to send message"})
    return JSONResponse(content={"status": "ok"})

# parse_message first to ensure data is uniform and the parser would not fail
async def auto_save_message(data: dict):
    if not Parser.is_messages_dir(messages_dir): 
        messages_dir.mkdir(parents=True, exist_ok=True)
    else:
        with open(messages_file, "r+") as f:
            messages = json.load(f)
            messages.append({"sender": data.get("sender"), "message": data.get("message"), "timestamp": time.time()})
            f.seek(0)
            json.dump(messages, f)

@app.get("/api/working_directory")
async def get_working_directory():
    import os
    return {"cwd": os.getcwd()}

@app.get("/service-offline.html")
async def service_offline():
    return FileResponse("../html/service-offline.html")

@app.get("/")
async def index():
    return FileResponse("../html/index.html")

@app.post("/api/send/{message}")
async def send_message(message: str):
    if not message:
        raise HTTPException(status_code=400, detail="Message content is required")

    # Process and send the message
    result = await send_via_lora(message)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to send message")

    return JSONResponse(content=result)

@app.post("/api/messages")
async def get_messages(checksum: str):
    if checksum != Parser.updated_messages_checksum(messages_file):
        json_response = {"status": "304", "message": "Checksum mismatch, Expected Requesting update of messages", "expected": Parser.updated_messages_checksum(messages_file), "received": checksum}
        raise JSONResponse(json_response)

    if not MessageStream.load_messages(messages_file):
        return JSONResponse(status_code=404, content={"status": "404", "message": "No messages found"})
    else:
        with open(messages_file, "r") as f:
            checksum = Parser.updated_messages_checksum(messages_file)
            from_user = Parser.parse_username(checksum)
            messages = json.load(f)
        return JSONResponse(content={"status": "200","user": from_user, "messages": messages, "checksum": checksum, "msg_status": "sent"})

@app.get("/api/checksum")
async def get_checksum():
    return JSONResponse(content={"checksum": checksum})

if __name__ == "__main__":
    import asyncio
    from uvicorn import Config, Server

    async def start_server():
        config = Config(app=app, host="0.0.0.0", port=5000, log_level="info", reload=False)
        server = Server(config)
        await server.serve()

    asyncio.run(start_server())

