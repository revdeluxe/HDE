import json, zlib

def encode_envelope(env: dict) -> bytes:
    payload = json.dumps(env, separators=(',',':')).encode('utf-8')
    crc     = zlib.crc32(payload) & 0xFFFFFFFF
    return crc.to_bytes(4, 'big') + payload

def decode_envelope(raw: bytes) -> dict:
    buf      = bytes(raw)
    crc_recv = int.from_bytes(buf[:4], 'big')
    payload  = buf[4:]
    if zlib.crc32(payload) & 0xFFFFFFFF != crc_recv:
        raise ValueError("CRC mismatch")
    return json.loads(payload.decode('utf-8'))
