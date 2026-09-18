"""
receiver.py
===========
SERVER side: handshake, then receives chunks using Go-Back-N rules.

Cumulative ACK logic: we ALWAYS reply with ack_num = "the next sequence
number I still need" - not "the packet I just got". This is what lets
one ACK confirm several packets at once, and it's also what tells the
sender exactly where to resume from after a loss (Go-Back-N: "go back
to sequence N and resend from there").

If a chunk arrives out of order (not the one we're expecting), we throw
its payload away and just re-send our current ACK - this is the "Go-Back-N"
part: the receiver refuses to buffer out-of-order data, so the sender is
forced to resend everything from the loss point onward.
"""

import socket
import random
from protocol.packet import Packet, FLAG_SYN, FLAG_ACK, FLAG_DATA, FLAG_FIN
from protocol.lossy_socket import LossySocket

HOST = "127.0.0.1"
PORT = 5005
LOSS_PROBABILITY = 0.15


def do_handshake(sock):
    print(f"[receiver] Listening on {HOST}:{PORT} ...")
    while True:
        data, client_addr = sock.recvfrom(2048)
        pkt = Packet.unpack(data)
        if pkt is None:
            continue

        if (pkt.flags & FLAG_SYN) and not (pkt.flags & FLAG_ACK):
            print(f"[receiver] Got SYN from {client_addr}, client seq={pkt.seq_num}")
            server_seq = random.randint(0, 10000)
            response = Packet(seq_num=server_seq, ack_num=pkt.seq_num + 1, flags=FLAG_SYN | FLAG_ACK)
            sock.sendto(response.pack(), client_addr)

            sock.settimeout(5)
            try:
                data2, addr2 = sock.recvfrom(2048)
                final_pkt = Packet.unpack(data2)
                if final_pkt and (final_pkt.flags & FLAG_ACK) and final_pkt.ack_num == server_seq + 1:
                    print("[receiver] Handshake complete.\n")
                    sock.settimeout(None)
                    return client_addr
            except socket.timeout:
                print("[receiver] Timed out waiting for final ACK, still listening for a new SYN...")
            sock.settimeout(None)


def receive_message(sock, client_addr):
    expected_seq = 0
    received_chunks = {}

    while True:
        data, addr = sock.recvfrom(2048)
        pkt = Packet.unpack(data)

        if pkt is None:
            print("[receiver] Dropped a corrupted packet (bad checksum)")
            continue

        if pkt.flags & FLAG_FIN:
            print("[receiver] Received FIN - message transfer complete\n")
            break

        if pkt.flags & FLAG_DATA:
            if pkt.seq_num == expected_seq:
                received_chunks[pkt.seq_num] = pkt.payload
                print(f"[receiver] Got chunk {pkt.seq_num} (in order) -> advancing")
                expected_seq += 1
            elif pkt.seq_num < expected_seq:
                print(f"[receiver] Got chunk {pkt.seq_num} again (duplicate/old) - re-ACKing")
            else:
                print(f"[receiver] Got chunk {pkt.seq_num} OUT OF ORDER "
                      f"(was expecting {expected_seq}) - discarding, re-ACKing what I actually have")

            ack_pkt = Packet(seq_num=0, ack_num=expected_seq, flags=FLAG_ACK)
            sock.sendto(ack_pkt.pack(), addr)

    full_message = b"".join(received_chunks[i] for i in sorted(received_chunks))
    print("=" * 60)
    print("[receiver] REASSEMBLED MESSAGE:")
    print(full_message.decode())
    print("=" * 60)


def run_receiver():
    real_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    real_sock.bind((HOST, PORT))
    sock = LossySocket(real_sock, loss_probability=LOSS_PROBABILITY)

    client_addr = do_handshake(sock)
    receive_message(sock, client_addr)

    print(f"\n[receiver] Network stats: {sock.stats()}")


if __name__ == "__main__":
    run_receiver()