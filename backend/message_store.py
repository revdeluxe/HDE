import os, json, time, uuid, socket, threading
from threading import Lock

STORE_FILE = 'messages.json'

class MessageStore:
    def __init__(self, filename, self_id=None):
        self.filename = filename
        # Set self_id to provided value or default to the hostname
        self.self_id = self_id or socket.gethostname()
        self._lock   = threading.Lock()
        self._msgs   = []      # ← initialize here
        self._load()
        # ensure file exists
        try:
            with open(self.filename, 'r') as f:
                pass
        except FileNotFoundError:
            with open(self.filename, 'w') as f:
                json.dump([], f)

    def _load(self):
        try:
            with open(STORE_FILE, 'r') as f:
                self._msgs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._msgs = []

    def _save(self):
        with open(STORE_FILE, 'w') as f:
            json.dump(self._msgs, f, indent=2)

    def add(self, sender, text, msg_id=None, ts=None, origin=None):
        origin = origin or self.self_id
        msg_id = msg_id or f"{sender}-{uuid.uuid4()}"
        ts     = ts or time.time()

        msg = { "id": msg_id, "from": sender, "message": text,
                "ts": ts, "origin": origin,
                "status": "pending" if origin == self.self_id else "received" }

        with self.lock:
            if not any(m["id"] == msg_id for m in self._msgs):
                self._msgs.append(msg)
                self._save()

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
