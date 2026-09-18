"""
sender.py
=========
CLIENT side: handshake, then sends a message using a SLIDING WINDOW with
real AIMD congestion control - a simplified Go-Back-N protocol.

Key difference from stop-and-wait: instead of 1 packet in flight at a
time, we keep up to `cwnd` packets in flight at once. cwnd grows on
success and collapses on loss, exactly like real TCP.

Uses cumulative ACKs: the receiver's ack_num means "I have everything
up to (but not including) this number, correctly, in order." So one ACK
can confirm multiple packets at once.
"""

import socket
import random
from protocol.packet import Packet, FLAG_SYN, FLAG_ACK, FLAG_DATA, FLAG_FIN
from protocol.lossy_socket import LossySocket
from protocol.congestion_control import AIMDCongestionControl

SERVER_ADDR = ("127.0.0.1", 5005)
MAX_RETRIES = 15
TIMEOUT_SECONDS = 0.5
MAX_PAYLOAD = 10
LOSS_PROBABILITY = 0.15

MESSAGE = (
    b"This is a longer message being sent using a sliding window with "
    b"real AIMD congestion control, so we can watch the window grow "
    b"during slow start, ease into congestion avoidance, and collapse "
    b"whenever a simulated packet loss triggers a timeout, just like TCP."
)


def do_handshake(sock):
    client_seq = random.randint(0, 10000)
    syn_pkt = Packet(seq_num=client_seq, ack_num=0, flags=FLAG_SYN)

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[sender] Handshake attempt {attempt}: sending SYN, seq={client_seq}")
        sock.sendto(syn_pkt.pack(), SERVER_ADDR)
        try:
            data, _ = sock.recvfrom(2048)
            reply = Packet.unpack(data)
            if reply and (reply.flags & FLAG_SYN) and (reply.flags & FLAG_ACK) \
                    and reply.ack_num == client_seq + 1:
                final_ack = Packet(seq_num=client_seq + 1, ack_num=reply.seq_num + 1, flags=FLAG_ACK)
                sock.sendto(final_ack.pack(), SERVER_ADDR)
                print("[sender] Handshake complete.\n")
                return True
        except socket.timeout:
            print("[sender] Handshake SYN lost, retrying...")
    print("[sender] Handshake failed. Is receiver.py running?")
    return False


def send_message_with_congestion_control(sock, message: bytes):
    chunks = [message[i:i + MAX_PAYLOAD] for i in range(0, len(message), MAX_PAYLOAD)]
    total = len(chunks)
    print(f"[sender] Message split into {total} chunks of up to {MAX_PAYLOAD} bytes each\n")

    cc = AIMDCongestionControl(initial_cwnd=1.0, initial_ssthresh=8.0)
    base = 0
    next_seq = 0

    def send_chunk(i):
        pkt = Packet(seq_num=i, ack_num=0, flags=FLAG_DATA, payload=chunks[i])
        sock.sendto(pkt.pack(), SERVER_ADDR)

    while base < total:
        window_end = min(total, base + cc.window_size())

        while next_seq < window_end:
            send_chunk(next_seq)
            next_seq += 1

        try:
            resp, _ = sock.recvfrom(2048)
            ack_pkt = Packet.unpack(resp)

            if ack_pkt and (ack_pkt.flags & FLAG_ACK) and ack_pkt.ack_num > base:
                newly_acked = ack_pkt.ack_num - base
                base = ack_pkt.ack_num
                for _ in range(newly_acked):
                    cc.on_ack()
                print(f"[sender] Cumulative ACK -> base={base}/{total}  "
                      f"cwnd={cc.cwnd:.2f}  ssthresh={cc.ssthresh:.1f}  "
                      f"window={cc.window_size()}")

        except socket.timeout:
            cc.on_loss()
            next_seq = base
            print(f"[sender] TIMEOUT at base={base} -> packet loss assumed. "
                  f"cwnd collapsed to {cc.cwnd:.2f}, ssthresh={cc.ssthresh:.1f}. Resending window.")

    fin_pkt = Packet(seq_num=total, ack_num=0, flags=FLAG_FIN)
    sock.sendto(fin_pkt.pack(), SERVER_ADDR)
    print("\n[sender] Sent FIN. Transfer complete!")
    cc.save_history_csv("cwnd_log.csv")
    print("[sender] Saved cwnd history to cwnd_log.csv (we'll graph this soon)")
    return cc


def run_sender():
    real_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    real_sock.settimeout(TIMEOUT_SECONDS)
    sock = LossySocket(real_sock, loss_probability=LOSS_PROBABILITY)

    if not do_handshake(sock):
        return

    send_message_with_congestion_control(sock, MESSAGE)
    print(f"\n[sender] Network stats: {sock.stats()}")


if __name__ == "__main__":
    run_sender()