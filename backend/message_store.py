import os, json, time, uuid, socket, threading
from threading import Lock

STORE_FILE = 'messages.json'

class MessageStore:
    def __init__(self, filename, self_id=None):
        self.filename = filename
        # Set self_id to provided value or default to the hostname
        self.self_id = self_id or socket.gethostname()
        self._lock   = threading.Lock()
        # ensure file exists
        try:
            with open(self.filename, 'r') as f:
                pass
        except FileNotFoundError:
            with open(self.filename, 'w') as f:
                json.dump([], f)

    def _load(self):
        try:
            with open(STORE_FILE) as f:
                self._msgs = json.load(f)
        except FileNotFoundError:
            self._msgs = []
        except json.JSONDecodeError:
            self._msgs = []

    def _save(self):
        with open(STORE_FILE, 'w') as f:
            json.dump(self._msgs, f, indent=2)

    def add(self, from_, message, timestamp=None, origin=None, status="pending"):
        # Use origin or fallback to self.self_id
        origin = origin or self.self_id

        msg = {
            "from":      from_,
            "message":   message,
            "timestamp": timestamp,
            "origin":    origin,
            "status":    status
        }
        with self._lock:
            with open(self.filename, 'r+') as f:
                data = json.load(f)
                data.append(msg)
                f.seek(0)
                json.dump(data, f, indent=2)
        return msg

    def all(self) -> list:
        with self._lock, open(self.filename, "r", encoding="utf-8") as f:
            return json.load(f)

    def append(self, msg: dict):
        with self._lock:
            data = []
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = []

            data.append(msg)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def confirm(self, msg_id):
        with self.lock:
            for m in self._msgs:
                if m["id"] == msg_id:
                    m["status"] = "confirmed"
                    self._save()
                    return True
        return False

    def checksum(self):
        """CRC32 of entire JSON bytes for sync-check."""
        import zlib
        data = json.dumps(self._msgs, separators=(',',':')).encode('utf-8')
        return zlib.crc32(data) & 0xFFFFFFFF

    def to_bytes(self):
        """Return raw JSON bytes for chunked sync."""
        return json.dumps(self._msgs, separators=(',',':')).encode('utf-8')
