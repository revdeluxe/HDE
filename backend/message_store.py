import os, json, time, uuid, socket
from threading import Lock

STORE_FILE = 'messages.json'

class MessageStore:
    def __init__(self, path: str):
        self.path = path
        self.lock = Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.isfile(path):
            with open(path, "w", encoding="utf-8") as f:
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

    def add(self, sender, text, msg_id=None, ts=None, origin=None):
        origin = origin or self.self_id
        msg_id = msg_id or f"{sender}-{uuid.uuid4()}"
        ts     = ts or time.time()
        msg = {
            "id":      msg_id,
            "from":    sender,
            "message": text,
            "ts":      ts,
            "origin":  origin,
            "status":  "pending" if origin == self.self_id else "received"
        }
        with self.lock:
            if not any(m["id"] == msg_id for m in self._msgs):
                self._msgs.append(msg)
                self._save()
        return msg

    def all(self):
        with self.lock:
            return list(self._msgs)

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
