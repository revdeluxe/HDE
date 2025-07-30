# parser.py

import hashlib
from pathlib import Path
from datetime import datetime

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
    def parse_message(raw: str) -> dict:
        """
        Parses structured LoRa message with CRC validation.
        Example: "from:node1|message:Hello|chunk_id:1|chunk_batch:3|timestamp:1722250340*AB"
        """
        result = {
            "original": raw,
            "valid": False,
            "error": None,
            "fields": {}
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
            parts = payload.split("|")
            for part in parts:
                if ":" not in part:
                    continue
                key, value = part.split(":", 1)
                result["fields"][key.strip()] = value.strip()

            # Basic validation
            required = ["from", "message", "chunk_id", "chunk_batch", "timestamp"]
            for key in required:
                if key not in result["fields"]:
                    result["error"] = f"Missing field: {key}"
                    return result

            # Type conversions
            result["fields"]["chunk_id"] = int(result["fields"]["chunk_id"])
            result["fields"]["chunk_batch"] = int(result["fields"]["chunk_batch"])
            result["fields"]["timestamp"] = int(result["fields"]["timestamp"])
            result["fields"]["timestamp_human"] = datetime.fromtimestamp(result["fields"]["timestamp"]).isoformat()

            result["valid"] = True
            return result

        except Exception as e:
            result["error"] = str(e)
            return result

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
    def get_chunks(data: bytes, chunk_size: int = 4096) -> list:
        """
        Splits a byte string into chunks of specified size (default 4096 bytes).
        """
        return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

    @staticmethod
    def reassemble_chunks(chunks: dict, batch_size: int) -> str:
        """
        Reassembles a complete message from a dict of chunks. Fills gaps with empty string.
        """
        return ''.join([chunks.get(i, '') for i in range(1, batch_size + 1)])

    @staticmethod
    def is_message_complete(chunks: dict, batch_size: int) -> bool:
        """
        Checks whether all chunks are present in a message batch.
        """
        return all(i in chunks for i in range(1, batch_size + 1))

    @staticmethod
    def repair_message(existing_chunks: dict, incoming_chunk: dict) -> tuple:
        """
        Attempts to repair an incomplete message by updating the chunk if valid.
        Returns the updated chunk map and a flag if message is now complete.
        """
        chunk_id = incoming_chunk["chunk_id"]
        chunk_batch = incoming_chunk["chunk_batch"]
        message_part = incoming_chunk["message"]

        existing_chunks[chunk_id] = message_part
        complete = Parser.is_message_complete(existing_chunks, chunk_batch)
        return existing_chunks, complete
