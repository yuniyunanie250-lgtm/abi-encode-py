"""ABI encoding, including dynamic types, in pure Python.

Static arguments occupy 32 bytes each. Dynamic ones (`string`, `bytes`, `T[]`)
live in a tail section and are referenced by an offset written into the head,
measured from the start of the argument block -- not from the start of the
calldata. Getting that wrong shifts every dynamic argument by the 4-byte
selector and produces a call that reverts with no useful diagnostic.
"""

import re

WORD = 32


class AbiError(ValueError):
    pass


def to_bytes(value, what="value"):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    s = value[2:] if isinstance(value, str) and value[:2].lower() == "0x" else value
    if not isinstance(s, str) or len(s) % 2:
        raise AbiError("%s: expected even-length hex, got %r" % (what, value))
    try:
        return bytes.fromhex(s)
    except ValueError:
        raise AbiError("%s: not hex: %r" % (what, value))


def word(value):
    """A non-negative int as one 32-byte word."""
    if value < 0:
        raise AbiError("word() takes an unsigned value, got %d" % value)
    if value >= 1 << 256:
        raise AbiError("value does not fit in 32 bytes")
    return value.to_bytes(32, "big")


def encode_word(kind, value):
    """Encode one static, single-word value."""
    if kind == "address":
        raw = to_bytes(value, "address")
        if len(raw) != 20:
            raise AbiError("address must be 20 bytes, got %d" % len(raw))
        return b"\x00" * 12 + raw
    if kind == "bool":
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return word(1 if value.lower() == "true" else 0)
        return word(1 if value else 0)
    m = re.fullmatch(r"bytes(\d+)", kind)
    if m:
        size = int(m.group(1))
        if not 1 <= size <= 32:
            raise AbiError("bad width in %s" % kind)
        raw = to_bytes(value, kind)
        if len(raw) != size:
            raise AbiError("%s needs %d bytes, got %d" % (kind, size, len(raw)))
        return raw + b"\x00" * (32 - len(raw))
    m = re.fullmatch(r"(u?int)(\d*)", kind)
    if m:
        bits = int(m.group(2)) if m.group(2) else 256
        if not 8 <= bits <= 256 or bits % 8:
            raise AbiError("bad width in %s" % kind)
        v = int(value)
        if m.group(1) == "int":
            limit = 1 << (bits - 1)
            if v < -limit or v >= limit:
                raise AbiError("%s out of range: %s" % (kind, value))
            if v < 0:
                v += 1 << 256
        else:
            if v < 0:
                raise AbiError("%s is unsigned: %s" % (kind, value))
            if bits < 256 and v >= 1 << bits:
                raise AbiError("%s out of range: %s" % (kind, value))
        return word(v)
    raise AbiError("unsupported type: %s" % kind)


def _pad_right(raw):
    rem = len(raw) % WORD
    return raw if rem == 0 else raw + b"\x00" * (WORD - rem)


def _encode_arg(kind, value):
    """(bytes, is_dynamic) for one argument."""
    if kind in ("bytes", "string"):
        raw = value.encode() if kind == "string" else to_bytes(value, "bytes")
        return word(len(raw)) + _pad_right(raw), True
    if kind.endswith("[]"):
        inner = kind[:-2]
        if inner in ("bytes", "string") or inner.endswith("[]"):
            raise AbiError("nested dynamic arrays are not supported: %s" % kind)
        parts = [_encode_arg(inner, v)[0] for v in value]
        return word(len(parts)) + b"".join(parts), True
    return encode_word(kind, value), False


def encode(args):
    """args: list of (type, value). Returns the argument block."""
    encoded = [_encode_arg(kind, value) for kind, value in args]
    head_size = WORD * len(encoded)
    head, tail, offset = [], [], head_size
    for blob, dynamic in encoded:
        if dynamic:
            head.append(word(offset))
            tail.append(blob)
            offset += len(blob)
        else:
            head.append(blob)
    return b"".join(head + tail)


def encode_call(selector, args=()):
    sel = to_bytes(selector, "selector")
    if len(sel) != 4:
        raise AbiError("selector must be 4 bytes, got %d" % len(sel))
    return "0x" + (sel + encode(list(args))).hex()


def decode_words(data):
    """Split a static argument block back into 32-byte words."""
    raw = to_bytes(data, "data")
    if len(raw) % WORD:
        raise AbiError("data is not a whole number of words: %d bytes" % len(raw))
    return [raw[i:i + WORD] for i in range(0, len(raw), WORD)]


def main(argv):
    import sys

    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("example: encode_call.py 0xa9059cbb address:0xd8da... uint256:1000")
        return 0
    selector = argv[0]
    args = []
    for a in argv[1:]:
        kind, _, value = a.partition(":")
        args.append((kind, value))
    print(encode_call(selector, args))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
