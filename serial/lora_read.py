import serial
import time
import json
import sqlite3
from pathlib import Path
import asyncio
import websockets

clients = set()

async def handler(websocket, path):
    clients.add(websocket)
    try:
        async for message in websocket:
            ser.write(message.encode())
    finally:
        clients.remove(websocket)

async def send_to_clients(message):
    if clients:
        await asyncio.gather(*(client.send(message) for client in clients))

async def serial_reader():
    while True:
        data = ser.readline().decode(errors='ignore').strip()
        if data:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            db_path = Path("../db/hde.sqlite3")
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("INSERT INTO lora_logs (timestamp, message) VALUES (?, ?)", (timestamp, data))
            conn.commit()
            conn.close()
            output = {
                "timestamp": timestamp,
                "message": data
            }
            await send_to_clients(json.dumps(output))
        await asyncio.sleep(0.1)

ser = serial.Serial("/dev/serial0", 9600, timeout=2)

async def main():
    ws_server = await websockets.serve(handler, "0.0.0.0", 8765)
    asyncio.create_task(serial_reader())
    await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
