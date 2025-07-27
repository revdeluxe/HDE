import struct
import time
import zlib
import json

PROTOCOL_VERSION = 1

# Header format (version, from_len, from_bytes, msg_len, msg_bytes, timestamp)
#   >B       = version
#   B{}s     = from_len + from_bytes
#   B{}s     = msg_len  + msg_bytes
#   I        = 4-byte timestamp
HEADER_FMT = ">B B{}s B{}s I"

def encode_message(msg):
    try:
        ts = int(time.mktime(
            time.strptime(msg['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")
        ))
    except Exception:
        ts = int(time.time())

    from_bytes    = msg['from'].encode('utf-8')
    message_bytes = msg['message'].encode('utf-8')
    header = HEADER_FMT.format(len(from_bytes), len(message_bytes))
    payload = struct.pack(
        header,
        PROTOCOL_VERSION,
        len(from_bytes), from_bytes,
        len(message_bytes), message_bytes,
        ts
    )
    crc = struct.pack(">I", zlib.crc32(payload))
    return payload + crc

def encode_chunks(payload, chunk_size=240):
    chunks = []
    total = len(payload)
    seq_num = 0

    for offset in range(0, total, chunk_size):
        chunk = payload[offset:offset + chunk_size]
        # Prefix with sequence ID
        prefixed = struct.pack(">B", seq_num % 256) + chunk
        chunks.append(prefixed)
        seq_num += 1

    return chunks

def decode_message(data):
    if isinstance(data, list):
        data = bytes(data)

    try:
        version = data[0]
        if version != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol version {version}")

        idx = 1
        from_len = data[idx]
        idx += 1
        from_str = data[idx:idx + from_len].decode('utf-8')
        idx += from_len

        msg_len = data[idx]
        idx += 1
        message = data[idx:idx + msg_len].decode('utf-8')
        idx += msg_len

        ts = struct.unpack(">I", data[idx:idx + 4])[0]
        idx += 4

        recv_crc = struct.unpack(">I", data[idx:idx + 4])[0]
        calc_crc = zlib.crc32(data[:idx])
        if recv_crc != calc_crc:
            raise ValueError("CRC mismatch")

        return {
            "from": from_str,
            "message": message,
            "timestamp": ts
        }

    except Exception as e:
        return {"error": str(e)}

def format_timestamp(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

def compare_with_existing_json(new_msg, cache_path="data/message.json"):
    try:
        with open(cache_path, "r") as f:
            old_msgs = json.load(f)
        old = old_msgs[-1] if old_msgs else {}
        return sum(1 for k in ("from", "message")
                   if new_msg.get(k) != old.get(k))
    except Exception:
        return 3

def calculate_quality(diff_score, latency,
                      max_latency=10, max_penalty=50):
    quality = 100
    quality -= diff_score * 20
    quality -= min(latency * 5, max_penalty)
    return max(quality, 0)

def crc_score(payload_bytes, message_cache="data/message.json"):
    now = int(time.time())
    decoded = decode_message(payload_bytes)
    if "error" in decoded:
        return 0

    diff = compare_with_existing_json(decoded, message_cache)
    latency = max(0, now - decoded.get("timestamp", now))
    quality = calculate_quality(diff, latency)

    try:
        with open(message_cache, "w") as f:
            json.dump([decoded], f)
    except OSError:
        pass

    return quality
