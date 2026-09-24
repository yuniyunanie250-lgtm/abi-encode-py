# abi-encode (Python)

ABI encoding in pure Python, including the dynamic types.

Static arguments are one 32-byte word each. Dynamic ones are the interesting
part: they go in a tail section, referenced by an offset in the head, which is
why an encoder needs the whole argument list at once and cannot encode one
argument in isolation.

## Usage

```bash
python3 abi_encode.py 0xa9059cbb address:0xd8da6bf2... uint256:1000000000000000000
```

```python
from abi_encode import encode_call

encode_call("0xa9059cbb", [
    ("address", "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"),
    ("uint256", "1000000000000000000"),
])
```

## Facts worth remembering

- **Offsets are relative to the start of the argument block**, so a single
  `string` argument always starts at offset 32 regardless of the selector.
- **`bytesM` means M bytes**, not M bits: `bytes4` is 4 bytes.
- **Signed integers are two's-complemented into a full 256-bit word**, and range
  checked against `M`.
- **Lengths are byte counts**, not character counts.

## What it does not do

- **No nested dynamic types.** `string[]` inside another dynamic array needs
  per-element offsets; refusing is better than emitting a wrong payload.
- **No tuples.** No ABI JSON parsing.
- **No decoding.** This package encodes; `decode_words` only slices static words
  so tests can inspect the output.

## Development

```bash
python3 -m unittest discover -s test -t .
```

## License

MIT
