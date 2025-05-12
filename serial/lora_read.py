# serial.py
import serial
import time
import json
import sqlite3
from pathlib import Path

# === Serial Config ===
ser = serial.Serial("/dev/serial0", 9600, timeout=2)
data = ser.readline().decode(errors='ignore').strip()
ser.close()

# === Timestamp ===
timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

# === Log to SQLite ===
db_path = Path("../db/HDE.sqlite3")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("INSERT INTO lora_logs (timestamp, message) VALUES (?, ?)", (timestamp, data or "No data"))
conn.commit()
conn.close()

# === Output JSON for WebSocket/HTTP ===
output = {
    "timestamp": timestamp,
    "message": data or "No data"
}

print(json.dumps(output))
