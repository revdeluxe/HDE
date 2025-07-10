<<<<<<< HEAD
import json, time, uuid, socket
from threading import Lock

STORE_FILE = 'messages.json'

class MessageStore:
    def __init__(self):
        self.lock   = Lock()
        self.self_id = socket.gethostname()
        self._load()

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
=======
import time, uuid

class MessageStore:
    def __init__(self):
        self._msgs = []    # list of dicts

    def add(self, sender, text, msg_id=None, ts=None):
        # generate stable, globally unique ID if not provided
        if msg_id is None:
            msg_id = f"{sender}-{uuid.uuid4()}"
        if ts is None:
            ts = time.time()
>>>>>>> 55e9d30b4c2fbdb827eafa73b3464c7e7165ba40
        msg = {
            "id":      msg_id,
            "from":    sender,
            "message": text,
<<<<<<< HEAD
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
=======
            "ts":      ts
        }
        # only append if new
        if not any(m["id"] == msg_id for m in self._msgs):
            self._msgs.append(msg)
        return msg

    def all(self):
        return list(self._msgs)

    def ids(self):
        return {m["id"] for m in self._msgs}
>>>>>>> 55e9d30b4c2fbdb827eafa73b3464c7e7165ba40
