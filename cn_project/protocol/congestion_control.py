"""
congestion_control.py
======================
This is the "brain" that decides HOW MANY packets we're allowed to have
unacknowledged (in flight) at once - the congestion window, or "cwnd".

Two phases, same as real TCP:
  SLOW START: cwnd grows FAST (roughly doubles each round trip) - because
              at the very start we have no idea how much the network can
              handle, so we probe aggressively until we hit trouble or a
              known-safe threshold.
  CONGESTION AVOIDANCE: cwnd grows SLOWLY (+1 per round trip) - once we're
              near the danger zone, we creep up cautiously instead of
              charging ahead.

On ANY timeout (packet loss), we assume the network is congested:
  - ssthresh (slow start threshold) is set to half our current window -
    "that's roughly the safe limit we now know about"
  - cwnd resets to 1 - "start over cautiously, probe from scratch"
This is the classic TCP Tahoe algorithm - simple, and very effective
at demonstrating the AIMD idea clearly.
"""


class AIMDCongestionControl:
    def __init__(self, initial_cwnd=1.0, initial_ssthresh=8.0):
        self.cwnd = initial_cwnd
        self.ssthresh = initial_ssthresh
        self.history = []  # list of (event_type, cwnd_after_event)

    def on_ack(self):
        """Called once for every chunk that gets successfully acknowledged."""
        if self.cwnd < self.ssthresh:
            self.cwnd += 1
            event = "ack (slow start)"
        else:
            self.cwnd += 1 / self.cwnd
            event = "ack (congestion avoidance)"
        self.history.append((event, round(self.cwnd, 2)))

    def on_loss(self):
        """Called when a timeout happens - we assume this means congestion/loss."""
        self.ssthresh = max(self.cwnd / 2, 1)
        self.cwnd = 1
        self.history.append(("LOSS - window reset", round(self.cwnd, 2)))

    def window_size(self) -> int:
        return max(1, int(self.cwnd))

    def save_history_csv(self, path="cwnd_log.csv"):
        with open(path, "w") as f:
            f.write("step,event,cwnd\n")
            for i, (event, cwnd) in enumerate(self.history):
                f.write(f"{i},{event},{cwnd}\n")