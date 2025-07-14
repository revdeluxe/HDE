import struct
import time
import zlib
import json

def encode_message(msg):
    try:
        ts = int(time.mktime(time.strptime(
            msg['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")))
    except Exception:
        ts = int(time.time())

    from_bytes    = msg['from'].encode('utf-8')
    message_bytes = msg['message'].encode('utf-8')

    payload = struct.pack(
        f">B{len(from_bytes)}sB{len(message_bytes)}sI",
        len(from_bytes),    from_bytes,
        len(message_bytes), message_bytes,
        ts
    )
    crc = struct.pack(">I", zlib.crc32(payload))
    return payload + crc

def encode_chunks(payload, chunk_size=240):
    return [payload[i:i+chunk_size] for i in range(0, len(payload), chunk_size)]

def format_timestamp(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

def decode_message(data):
    try:
        from_len = data[0]
        from_str = data[1:1+from_len].decode('utf-8')

        msg_len   = data[1+from_len]
        msg_start = 2 + from_len
        message   = data[msg_start:msg_start+msg_len].decode('utf-8')

        ts_start = msg_start + msg_len
        ts       = struct.unpack(">I", data[ts_start:ts_start+4])[0]

        crc_recv = struct.unpack(">I", data[ts_start+4:ts_start+8])[0]
        if zlib.crc32(data[:ts_start+4]) != crc_recv:
            raise ValueError("CRC mismatch")

        return {"from": from_str, "message": message, "timestamp": ts}

    except Exception as e:
        return {"error": str(e)}
    
def decode_chunks(chunks):
    if not chunks:
        return {}
    try:
        data = b"".join(chunks)
        return json.loads(data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return {"error": str(e)}

def compare_with_existing_json(new_msg, cache_path="data/message.json"):
    try:
        with open(cache_path, "r") as f:
            old_msgs = json.load(f)
        old_msg = old_msgs[-1] if old_msgs else {}
        return sum(1 for k in ("from","message")
                   if new_msg.get(k) != old_msg.get(k))
    except Exception:
        return 3  # max diff score fallback

def calculate_quality(diff_score, latency,
                      max_latency=10, max_penalty=50):
    quality = 100
    quality -= diff_score * 20
    quality -= min(latency * 5, max_penalty)
    return max(quality, 0)

def crc_score(payload_bytes, message_cache="data/message.json"):
    current_ts = int(time.time())
    decoded    = decode_message(payload_bytes)
    if "error" in decoded:
        return 0

    # 1) compute quality
    diff_score = compare_with_existing_json(decoded, message_cache)
    latency    = current_ts - decoded["timestamp"]
    quality    = calculate_quality(diff_score, latency)

    # 2) update cache for next comparison
    try:
        # store as a single-element list or append to history
        with open(message_cache, "w") as f:
            json.dump([decoded], f)
    except OSError:
        pass

    return quality

