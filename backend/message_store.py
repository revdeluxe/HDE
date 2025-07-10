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
        msg = {
            "id":      msg_id,
            "from":    sender,
            "message": text,
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
