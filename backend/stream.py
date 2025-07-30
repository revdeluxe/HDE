# stream.py

import time
import json
from pathlib import Path
from parser import Parser

class MessageStream:
    def __init__(self, timeout=60):
        """
        Handles chunked LoRa message reassembly and storage.
        """
        self.buffers = {}  # {sender: {"timestamp": last_updated, "chunks": {id: message}, "batch": total}}
        self.timeout = timeout  # Timeout in seconds for incomplete messages

    def add_chunk(self, sender: str, chunk_id: int, chunk_batch: int, message: str, timestamp: int):
        """
        Adds a chunk to the buffer and attempts reassembly.
        Returns:
            - None if still incomplete
            - Assembled message (string) if complete
        """
        if sender not in self.buffers:
            self.buffers[sender] = {
                "timestamp": time.time(),
                "chunks": {},
                "batch": chunk_batch
            }

        buf = self.buffers[sender]
        buf["chunks"][chunk_id] = message
        buf["timestamp"] = time.time()

        if Parser.is_message_complete(buf["chunks"], buf["batch"]):
            full_message = Parser.reassemble_chunks(buf["chunks"], buf["batch"])
            del self.buffers[sender]
            return full_message

        return None

    def cleanup(self):
        """
        Removes old/incomplete messages past timeout threshold.
        Should be called periodically.
        """
        now = time.time()
        expired = [k for k, v in self.buffers.items() if now - v["timestamp"] > self.timeout]
        for key in expired:
            del self.buffers[key]

    def messages_path() -> Path:
        """
        Returns the path to the messages.json file.
        """
        return Path("messages/messages.json")

    def load_messages(self, sender: str = None):
        """
        Loads messages.json and optionally filters by sender.
        """
        path = self.messages_path()
        if not path.exists():
            return []

        with path.open("r", encoding="utf-8") as f:
            try:
                all_messages = json.load(f)
            except json.JSONDecodeError:
                return []

        if sender:
            return [msg for msg in all_messages if msg.get("from") == sender]
        return all_messages

    def save_message(self, sender: str, message: str, timestamp: int):
        """
        Saves a fully reassembled message to messages.json.
        """
        path = self.messages_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        new_entry = {
            "from": sender,
            "message": message,
            "timestamp": timestamp,
            "timestamp_human": time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(timestamp))
        }

        messages = self.load_messages()
        messages.append(new_entry)

        with path.open("w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2)

        return new_entry
