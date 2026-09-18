"""
packet.py
=========
This defines the HEADER FORMAT of our custom transport protocol.

Think of this like designing our own mini version of a TCP header.
Every packet we send will have:
  - seq_num   : sequence number of THIS packet (like a page number)
  - ack_num   : which sequence number we are acknowledging (confirming receipt of)
  - flags     : what TYPE of packet this is (SYN, ACK, FIN, or DATA)
  - checksum  : a number used to detect if the packet got corrupted in transit
  - payload   : the actual data being sent (e.g. part of a file, or a chat message)

We use Python's `struct` module to convert these fields into raw BYTES,
because that is what actually travels over a network - not Python objects,
not JSON, just a tightly packed sequence of bytes. This is exactly how
real protocols like TCP/IP work under the hood.
"""

import struct

# --- Flags: these are like switches that say what kind of packet this is ---
# We use bit flags (powers of 2) so multiple flags can be combined in ONE byte
# using bitwise OR, e.g. SYN + ACK together = 0x01 | 0x02 = 0x03
FLAG_SYN = 0x01   # "I want to start a connection" (used in handshake)
FLAG_ACK = 0x02   # "I am acknowledging a packet you sent me"
FLAG_FIN = 0x04   # "I am done sending, closing the connection"
FLAG_DATA = 0x08  # "This packet carries real payload data"

# --- Header layout ---
# '!' means network byte order (big-endian) - the standard for all network protocols
# 'I' = unsigned 4-byte integer   -> used for seq_num and ack_num
# 'B' = unsigned 1-byte integer   -> used for flags
# 'H' = unsigned 2-byte integer   -> used for checksum
# So our header is 4 + 4 + 1 + 2 = 11 bytes, always, no matter the payload size.
HEADER_FORMAT = "!IIBH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # will print 11


def compute_checksum(data: bytes) -> int:
    """
    A simplified version of the classic 'Internet checksum' algorithm
    (the same style of checksum used in real IP/TCP/UDP headers).

    How it works in plain terms:
      1. Break the data into 2-byte chunks.
      2. Add all the chunks together.
      3. If the sum overflows 16 bits, wrap the overflow back around and add it in
         (this is called "one's complement addition").
      4. Flip all the bits at the end (the "complement" part).

    Why this matters: if even ONE bit gets corrupted during transmission,
    the checksum computed by the receiver will NOT match the checksum we
    sent - so the receiver knows to discard the packet and ask for it again.
    """
    if len(data) % 2 == 1:
        data += b"\x00"  # pad with a zero byte if odd length

    total = 0
    for i in range(0, len(data), 2):
        chunk = (data[i] << 8) + data[i + 1]
        total += chunk
        total = (total & 0xFFFF) + (total >> 16)  # wrap-around carry

    return (~total) & 0xFFFF  # flip bits, keep it within 16 bits


class Packet:
    """
    Represents ONE packet in our protocol: header + payload.
    Has two jobs: pack() turns it into bytes to send on the wire,
    unpack() turns received bytes back into a usable Packet object.
    """

    def __init__(self, seq_num=0, ack_num=0, flags=0, payload=b""):
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.flags = flags
        self.payload = payload

    def pack(self) -> bytes:
        """Convert this packet into raw bytes ready to send over UDP."""
        header_without_checksum = struct.pack(
            "!IIB", self.seq_num, self.ack_num, self.flags
        )
        checksum = compute_checksum(header_without_checksum + self.payload)

        header = struct.pack(
            HEADER_FORMAT, self.seq_num, self.ack_num, self.flags, checksum
        )
        return header + self.payload

    @staticmethod
    def unpack(data: bytes):
        """
        Convert raw bytes received from the network back into a Packet object.
        Also verifies the checksum - returns None if the packet is corrupted.
        """
        if len(data) < HEADER_SIZE:
            return None  # too short to even have a valid header - drop it

        header = data[:HEADER_SIZE]
        payload = data[HEADER_SIZE:]

        seq_num, ack_num, flags, received_checksum = struct.unpack(HEADER_FORMAT, header)

        header_without_checksum = struct.pack("!IIB", seq_num, ack_num, flags)
        expected_checksum = compute_checksum(header_without_checksum + payload)

        if expected_checksum != received_checksum:
            return None  # corrupted packet - caller should treat this as packet loss

        return Packet(seq_num, ack_num, flags, payload)

    def __repr__(self):
        flag_names = []
        if self.flags & FLAG_SYN:
            flag_names.append("SYN")
        if self.flags & FLAG_ACK:
            flag_names.append("ACK")
        if self.flags & FLAG_FIN:
            flag_names.append("FIN")
        if self.flags & FLAG_DATA:
            flag_names.append("DATA")
        return (f"Packet(seq={self.seq_num}, ack={self.ack_num}, "
                f"flags={'+'.join(flag_names) or 'NONE'}, "
                f"payload={len(self.payload)} bytes)")