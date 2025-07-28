import os, json, time, uuid, socket, threading
from threading import Lock

STORE_FILE = 'messages.json'

class MessageStore:
    def __init__(self, filename, self_id=None):
        self.lock = Lock()
        self.filename = filename
        # Set self_id to provided value or default to the hostname
        self.self_id = self_id or socket.gethostname()
        self._lock   = threading.Lock()
        self._msgs  = []
        self.path   = os.path.abspath(filename)
        self.messages: Dict[int, Dict[str, Any]] = {}
        self._load()
        # ensure file exists
        try:
            with open(self.filename, 'r') as f:
                pass
        except FileNotFoundError:
            with open(self.filename, 'w') as f:
                json.dump([], f)

    def _load(self) -> None:
        try:
            with open(self.path, 'r') as f:
                data: List[Dict[str, Any]] = json.load(f)
            for msg in data:
                self.messages[msg['id']] = msg
        except FileNotFoundError:
            self.messages = {}

    def _save(self) -> None:
        with open(self.path, 'w') as f:
            json.dump(list(self.messages.values()), f, indent=2)

    def compute_crc(self, msg: Dict[str, Any]) -> int:
        # Exclude the crc field itself when computing
        payload = {
            k: msg[k] for k in sorted(msg)
            if k not in ('crc',)
        }
        raw = json.dumps(payload, separators=(',',':')).encode()
        return zlib.crc32(raw) & 0xFFFFFFFF

    def add(self, sender: str, text: str, ts: float, origin: str) -> Dict[str, Any]:
        new_id = max(self.messages.keys(), default=0) + 1
        msg = {
            'id':      new_id,
            'from':    sender,
            'message': text,
            'timestamp': ts,
            'origin':  origin,
        }
        msg['crc'] = self.compute_crc(msg)
        self.messages[new_id] = msg
        self._save()
        return msg

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self.messages.values())

    def get_crc_map(self) -> Dict[int, int]:
        return {mid: m['crc'] for mid, m in self.messages.items()}

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
