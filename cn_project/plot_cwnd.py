"""
plot_cwnd.py
============
Reads cwnd_log.csv (generated automatically by sender.py after each run)
and draws the classic congestion-window "sawtooth" graph - the single
most recognizable visual in networking.

Run this AFTER running sender.py at least once:
    python3 plot_cwnd.py
It will open a window with the graph, and also save it as cwnd_graph.png
so you can drop it straight into your README or a report.
"""

import csv
import matplotlib.pyplot as plt


def load_cwnd_log(path="cwnd_log.csv"):
    steps, cwnds, is_loss = [], [], []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            steps.append(int(row["step"]))
            cwnds.append(float(row["cwnd"]))
            is_loss.append("LOSS" in row["event"])
    return steps, cwnds, is_loss


def plot(steps, cwnds, is_loss, save_path="cwnd_graph.png"):
    plt.figure(figsize=(11, 5))

    plt.plot(steps, cwnds, color="#0E7C7B", linewidth=2, label="Congestion window (cwnd)")

    loss_steps = [s for s, loss in zip(steps, is_loss) if loss]
    loss_cwnds = [c for c, loss in zip(cwnds, is_loss) if loss]
    plt.scatter(loss_steps, loss_cwnds, color="#D62828", zorder=5, label="Packet loss (timeout)")

    plt.title("Congestion Window Over Time - AIMD Sawtooth Pattern", fontsize=13, fontweight="bold")
    plt.xlabel("Event step (each ACK or loss)")
    plt.ylabel("cwnd (packets allowed in flight)")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"Saved graph to {save_path}")
    plt.show()


if __name__ == "__main__":
    steps, cwnds, is_loss = load_cwnd_log("cwnd_log.csv")
    print(f"Loaded {len(steps)} events from cwnd_log.csv")
    plot(steps, cwnds, is_loss)