"""
lossy_socket.py
================
Wraps a real UDP socket and randomly DROPS outgoing packets on purpose,
to simulate a bad/unreliable network - the same kind of thing tools like
Linux 'tc netem' do for real testing.

Why this matters: on localhost (127.0.0.1), real packet loss is basically
0%. If we never test with loss, we can never actually PROVE our retransmit
logic works - we'd just be hoping. This lets us watch it happen on purpose.
"""

import random


class LossySocket:
    def __init__(self, real_socket, loss_probability=0.0):
        self._sock = real_socket
        self.loss_probability = loss_probability
        self.dropped_count = 0
        self.sent_count = 0

    def sendto(self, data, addr):
        self.sent_count += 1
        if random.random() < self.loss_probability:
            self.dropped_count += 1
            # We pretend to send it (return the byte count like a real socket would)
            # but never actually call the real sendto - the packet vanishes.
            return len(data)
        return self._sock.sendto(data, addr)

    def recvfrom(self, bufsize):
        return self._sock.recvfrom(bufsize)

    def settimeout(self, t):
        self._sock.settimeout(t)

    def bind(self, addr):
        self._sock.bind(addr)

    def close(self):
        self._sock.close()

    def stats(self):
        loss_pct = (self.dropped_count / self.sent_count * 100) if self.sent_count else 0
        return f"sent={self.sent_count}, dropped={self.dropped_count} ({loss_pct:.1f}%)"