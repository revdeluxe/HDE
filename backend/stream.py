import time
import json
from pathlib import Path
from parser import Parser

try:
    import aiofiles
except ImportError:
    aiofiles = None  # Fallback if async isn't required


class MessageStream:
    def __init__(self, timeout=60):
        """
        Handles chunked LoRa message reassembly and storage.
        """
        self._path = Path("backend/messages/messages.json")
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

    def load_messages(self):
        """
        Loads messages synchronously.
        """
        if not self._path.is_file():
            return []
        with self._path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_message(self, sender: str, message: str, timestamp: int):
        """
        Saves a fully reassembled message synchronously.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)

        new_entry = {
            "from": sender,
            "message": message,
            "timestamp": timestamp,
            "timestamp_human": time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(timestamp))
        }

        messages = self.load_messages()
        messages.append(new_entry)

        with self._path.open("w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2)

        return new_entry

    # Optional async versions if aiofiles is available
    async def load_messages_async(self):
        if not aiofiles or not self._path.is_file():
            return []
        async with aiofiles.open(self._path, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)

    async def save_message_async(self, sender: str, message: str, timestamp: int):
        """
        Saves a fully reassembled message asynchronously using aiofiles.
        """
        if not aiofiles:
            raise RuntimeError("aiofiles is not available")

        self._path.parent.mkdir(parents=True, exist_ok=True)

        new_entry = {
            "from": sender,
            "message": message,
            "timestamp": timestamp,
            "timestamp_human": time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(timestamp))
        }

        messages = await self.load_messages_async()
        messages.append(new_entry)

        async with aiofiles.open(self._path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(messages, indent=2))

        return new_entry
