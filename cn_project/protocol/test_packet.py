"""
test_packet.py
===============
Quick sanity tests for our packet format before we build anything on top of it.
Run this with:  python3 -m protocol.test_packet
(from inside the cn_project folder)
"""

from protocol.packet import Packet, FLAG_SYN, FLAG_ACK, FLAG_DATA


def test_pack_unpack_roundtrip():
    """A packet should survive being packed to bytes and unpacked back unchanged."""
    original = Packet(seq_num=42, ack_num=0, flags=FLAG_DATA, payload=b"hello network")
    raw_bytes = original.pack()
    rebuilt = Packet.unpack(raw_bytes)

    assert rebuilt is not None, "Unpack failed on a valid, uncorrupted packet!"
    assert rebuilt.seq_num == 42
    assert rebuilt.ack_num == 0
    assert rebuilt.flags == FLAG_DATA
    assert rebuilt.payload == b"hello network"
    print("PASS: pack -> unpack round trip works correctly")
    print(f"  original: {original}")
    print(f"  rebuilt : {rebuilt}")


def test_checksum_catches_corruption():
    """If we flip a bit in the payload after sending, unpack() must detect it and return None."""
    pkt = Packet(seq_num=1, ack_num=0, flags=FLAG_SYN | FLAG_ACK, payload=b"important data")
    raw_bytes = bytearray(pkt.pack())

    # Simulate corruption: flip one bit in the payload (as if a noisy network mangled it)
    raw_bytes[-1] ^= 0xFF

    result = Packet.unpack(bytes(raw_bytes))
    assert result is None, "Checksum failed to catch corrupted data!"
    print("PASS: checksum correctly detects a corrupted packet and rejects it")


def test_header_size():
    from protocol.packet import HEADER_SIZE
    assert HEADER_SIZE == 11, f"Expected 11-byte header, got {HEADER_SIZE}"
    print(f"PASS: header size is {HEADER_SIZE} bytes (4 seq + 4 ack + 1 flags + 2 checksum)")


if __name__ == "__main__":
    test_header_size()
    test_pack_unpack_roundtrip()
    test_checksum_catches_corruption()
    print("\nAll packet-level tests passed. Foundation is solid.")