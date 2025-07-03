import json
import os
import threading
from datetime import datetime

class MessageStore:
    def __init__(self, path='data/messages.json'):
        self.path = path
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, 'w') as f:
                json.dump([], f)

    def _load(self):
        with open(self.path, 'r') as f:
            return json.load(f)

    def _save(self, data):
        tmp = self.path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)

    def add(self, sender, text):
        msg = {
            'from': sender,
            'message': text,
            'timestamp': datetime.utcnow().isoformat()
        }
        with self.lock:
            data = self._load()
            data.append(msg)
            self._save(data)
        return msg

    def all(self):
        with self.lock:
            return self._load()
