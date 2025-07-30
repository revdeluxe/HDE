# parser.py

import hashlib, json, re
from pathlib import Path
from datetime import datetime, time

DATA_DIR = Path("messages")
TO_SEND_PATH = DATA_DIR / "to_send.json"
CHUNK_DATA_PATH = DATA_DIR / "chunk_data.json"

class Parser:
    def __init__(self):
        self.max_chunk_size = 240  # Maximum chunk size in bytes

    @staticmethod
    def calculate_crc(payload: str) -> str:
        """Simple XOR-based checksum"""
        crc = 0
        for char in payload:
            crc ^= ord(char)
        return format(crc, "02X")
    
    @staticmethod
    def prepare(data: dict) -> str:
        """
        Prepares a structured LoRa message with CRC.
        Example: "from:node1|message:Hello|chunk_id:1|chunk_batch:3|timestamp:1722250340*AB"
        """
        fields = [
            f"from:{data['from']}",
            f"message:{data['message']}",
            f"checksum:{data['checksum']}",
            f"chunk_id:{data['chunk_id']}",
            f"chunk_batch:{data['chunk_batch']}",
            f"timestamp:{data['timestamp']}"
        ]
        payload = "|".join(fields)
        crc = Parser.calculate_crc(payload)
        return f"{payload}*{crc}"

    @staticmethod
    def parse_message(raw: str) -> dict:
        """
        Parses structured LoRa message with CRC validation.
        Example: "from:node1|message:Hello|chunk_id:1|chunk_batch:3|timestamp:1722250340*AB"
        """
        result = {
            "from": None,
            "timestamp": None,
            "batch": None,
            "chunk": [],
            "valid": False,
            "error": None
        }

        try:
            if "*" not in raw:
                result["error"] = "CRC delimiter not found."
                return result

            payload, crc = raw.rsplit("*", 1)
            expected_crc = Parser.calculate_crc(payload)

            if crc.upper() != expected_crc:
                result["error"] = f"CRC mismatch (expected {expected_crc}, got {crc.upper()})"
                return result

            # Split fields by |
            fields = payload.split("|")
            for field in fields:
                if ":" not in field:
                    continue
                key, value = field.split(":", 1)
                if key == "from":
                    result["from"] = value
                elif key == "timestamp":
                    try:
                        result["timestamp"] = int(value)
                    except ValueError:
                        result["error"] = "Invalid timestamp format."
                        return result
                elif key == "chunk_batch":
                    try:
                        result["batch"] = int(value)
                    except ValueError:
                        result["error"] = "Invalid chunk batch format."
                        return result
                elif key == "message":
                    # If message contains multiple chunks
                    if "|c" in value:
                        chunks = re.findall(r"\|c(\d+)\|([^|]+)", value)
                        for cid, msg in chunks:
                            result["chunk"].append({"id": int(cid), "message": msg})
                    else:
                        result["chunk"].append({"id": 1, "message": value})

            # Basic validation
            if not result["from"] or not result["timestamp"] or not result["batch"]:
                result["error"] = "Missing required fields."
                return result

            result["valid"] = True
            return result

        except Exception as e:
            result["error"] = str(e)
            return result
        
    @staticmethod
    def parse_username(checksum: str) -> str:
        """
        Parses a username from a checksum string.
        Example: "user:john_doe|checksum:1234567890"
        """
        if not checksum or "|" not in checksum:
            return None

        parts = checksum.split("|")
        for part in parts:
            if part.startswith("user:"):
                return part.split(":", 1)[1].strip()
        return None
        
    @staticmethod
    def updated_messages_checksum(path: Path) -> str:
        """
        Returns the CRC32 checksum of messages.json.
        If file does not exist, returns "FILE_NOT_FOUND".
        """
        if not path.exists():
            return "FILE_NOT_FOUND"
        return Parser.file_crc32(path)

    @staticmethod
    def file_crc32(path: Path) -> str:
        """
        Calculates CRC32 of a file. Returns hex string (e.g. 'A1B2C3D4').
        """
        crc = 0
        try:
            with path.open("rb") as f:
                while chunk := f.read(4096):
                    for byte in chunk:
                        crc ^= byte
                        for _ in range(8):
                            if crc & 1:
                                crc = (crc >> 1) ^ 0xEDB88320
                            else:
                                crc >>= 1
            return format(crc & 0xFFFFFFFF, '08X')
        except FileNotFoundError:
            return "FILE_NOT_FOUND"

    @staticmethod
    def file_md5(path: Path) -> str:
        """
        Alternative: Get MD5 hash of file for more robust validation.
        """
        try:
            hash_md5 = hashlib.md5()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except FileNotFoundError:
            return "FILE_NOT_FOUND"

    @staticmethod
    def check_crc_diffs(path1: Path, path2: Path) -> bool:
        """
        Compares CRC32 of two files. Returns True if they differ.
        """
        crc1 = Parser.file_crc32(path1)
        crc2 = Parser.file_crc32(path2)

        if crc1 == "FILE_NOT_FOUND" or crc2 == "FILE_NOT_FOUND":
            return False  # One of the files does not exist

        return crc1 != crc2

    @staticmethod
    def is_messages_dir(path: Path) -> bool:
        """
        Checks if a directory is a valid messages directory.
        It should contain 'messages.json' and 'to_send.json'.
        """
        if not path.is_dir():
            return False
        if not (path / "messages.json").exists() or not (path / "to_send.json").exists():
            return False
        return True

    @staticmethod
    def should_it_be_in_batches(batch: dict, max_chunk_size: int = 240) -> bool:
        """
        Determines if the data should be sent in batches based on size.
        """
        chunks = batch.get("chunks", [])
        chunk_size = sum(len(chunk.encode('utf-8')) for chunk in chunks)
        total_size = len(batch.get("message", "").encode('utf-8'))

        if chunk_size <= 0 or total_size <= 0:
            return False

        if total_size > max_chunk_size:
            return True

        return False
    
    @staticmethod
    def split_into_chunks(message: str, max_size: int = 240) -> list:
        """
        Splits the message into UTF-8 safe chunks not exceeding `max_size` bytes.
        Adds a marshal to identify if data is a split chunk with chunk identifiers.
        """
        chunks = []
        current_chunk = ""
        chunk_id = 1

        for char in message:
            # Check if adding the char exceeds the byte limit
            if len((current_chunk + char).encode('utf-8')) > max_size:
                chunks.append(f"|c{chunk_id}|{current_chunk}")
                current_chunk = char
                chunk_id += 1
            else:
                current_chunk += char

        if current_chunk:
            chunks.append(f"|c{chunk_id}|{current_chunk}")

        return chunks

    @staticmethod
    def is_it_in_batches(message: str, max_size: int = 240) -> bool:
        """
        Checks if the message is already split into chunks or contains a split chunk marshal.
        """
        if not message:
            return False

        # Check for split chunk marshal pattern
        if any(f"|c{i}|" in message for i in range(1, 1000)):  # Arbitrary upper limit for chunk IDs
            return True

        # Check if the message exceeds the maximum size
        if len(message.encode('utf-8')) > max_size:
            return True

        return False

    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            with open(path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _save_json(path: Path, data: dict) -> None:
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def load_chunk(chunk_batch: int) -> dict:
        """
        Loads a specific chunk batch from chunk_data.json.
        """
        chunks = Parser._load_json(Parser.CHUNK_DATA_PATH)
        return chunks.get(str(chunk_batch), {})

    @staticmethod
    def last_chunk_id(path: Path = TO_SEND_PATH) -> int:
        """
        Returns the last chunk ID from the to_send.json file.
        """
        chunks = Parser._load_json(path)
        return max((int(k) for k in chunks), default=0)

    @staticmethod
    def last_batch_id(path: Path = TO_SEND_PATH) -> int:
        """
        Returns the last batch ID from the to_send.json file.
        """
        chunks = Parser._load_json(path)
        return max((int(v.get("chunk_batch", 0)) for v in chunks.values()), default=0)

    @staticmethod
    def generate_batch_id() -> int:
        """
        Generates a new batch ID based on the last one.
        """
        return Parser.last_batch_id() + 1   

    @staticmethod
    def batch_chunks(chunks: list, batch_size: int, sender: str) -> dict:
        """
        Groups chunks into batches with specified size and includes metadata.
        """
        batch_id = Parser.last_batch_id() + 1
        batch = {}
        timestamp = int(datetime.now().timestamp())

        for i, chunk in enumerate(chunks):
            chunk_id = i + 1
            batch[chunk_id] = {
                "from": sender,
                "message": chunk,
                "chunk_id": chunk_id,
                "chunk_batch": batch_id,
                "timestamp": timestamp
            }

        return {
            "from": sender,
            "timestamp": timestamp,
            "batch": batch_id,
            "chunk": list(batch.values())
        }

    @staticmethod
    def get_batch_chunks(batch: int, path: Path = TO_SEND_PATH) -> dict:
        """
        Loads a specific batch of chunks from the to_send.json file.
        """
        chunks = Parser._load_json(path)
        return {k: v for k, v in chunks.items() if int(k) <= batch}

    @staticmethod
    def generate_chunk_id() -> int:
        """
        Generates a unique chunk ID based on last_chunk_id.
        """
        return Parser.last_chunk_id() + 1

    @staticmethod
    def save_chunk_data(sender, timestamp, batch, chunk_id, message):
        file_path = os.path.join(SAVE_DIR, f"{sender}_{timestamp}_{batch}.json")

        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
        else:
            data = {}

        data[str(chunk_id)] = message

        with open(file_path, "w") as f:
            json.dump(data, f)

    @staticmethod
    def get_chunks(data: bytes, chunk_size: int = 4096) -> list:
        """
        Splits a byte string into fixed-size chunks.
        """
        return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

    @staticmethod
    def chunk_message(message, max_length=240):
        if len(message) <= max_length:
            return [{"id": 1, "text": message}]
        
        chunks = []
        lines = [message[i:i+max_length] for i in range(0, len(message), max_length)]
        for idx, line in enumerate(lines, 1):
            chunks.append({"id": idx, "text": f"|c{idx}|{line}"})
        return chunks


    @staticmethod
    def reassemble_chunks(sender, timestamp, batch):
        file_path = os.path.join(SAVE_DIR, f"{sender}_{timestamp}_{batch}.json")
        if not os.path.exists(file_path):
            return ""

        with open(file_path, "r") as f:
            data = json.load(f)

        chunks = [data[key] for key in sorted(data, key=lambda x: int(x))]
        return "".join([chunk.split("|", 1)[-1] if "|c" in chunk else chunk for chunk in chunks])


    @staticmethod
    def is_message_complete(chunks: dict, batch_size: int) -> bool:
        """
        Checks if all expected chunks are present.
        """
        return all(i in chunks for i in range(1, batch_size + 1))

    @staticmethod
    def repair_message(existing_chunks: dict, incoming_chunk: dict) -> tuple:
        """
        Attempts to repair a message by updating with a new chunk.
        """
        chunk_id = incoming_chunk["chunk_id"]
        message_part = incoming_chunk["message"]
        batch_size = incoming_chunk.get("expected_chunks", len(existing_chunks))  # Or pass explicitly
        existing_chunks[chunk_id] = message_part
        complete = Parser.is_message_complete(existing_chunks, batch_size)
        return existing_chunks, complete
