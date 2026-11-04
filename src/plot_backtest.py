"""P&L chart of the June 2025 hedging backtest (reads hedge_paths.csv).

One panel, one axis: hourly P&L per $100 of exposure for the unhedged
short-crude book and the mark-to-market P&L of each $5 hedge. Colors follow
the validated reference palette; weekends (futures closed) shaded.
Output: data/episode_jun2025/backtest_jun2025.png
"""
import csv
import datetime as dt
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
EP = os.path.join(os.path.dirname(HERE), "data", "episode_jun2025")

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASE = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
PREMIUM = 5.0


def main():
    ts, expo, dig, hor, usa = [], [], [], [], []
    with open(os.path.join(EP, "hedge_paths.csv")) as f:
        for r in csv.DictReader(f):
            ts.append(dt.datetime.fromtimestamp(int(r["ts"]), dt.timezone.utc))
            expo.append(float(r["exposure_pnl"]))
            dig.append(float(r["digital"]) - PREMIUM)
            hor.append(float(r["hormuz"]) - PREMIUM)
            usa.append(float(r["us_action_aug"]) - PREMIUM)

    fig, ax = plt.subplots(figsize=(11, 5), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for a, b in [(dt.datetime(2025, 6, 20, 21, tzinfo=dt.timezone.utc),
                  dt.datetime(2025, 6, 22, 22, tzinfo=dt.timezone.utc)),
                 (dt.datetime(2025, 6, 27, 21, tzinfo=dt.timezone.utc),
                  dt.datetime(2025, 6, 29, 22, tzinfo=dt.timezone.utc))]:
        ax.axvspan(a, b, color=GRID, alpha=0.45, linewidth=0)

    series = [(expo, BLUE, "Unhedged exposure (short crude, $100)"),
              (dig, ORANGE, "Digital call 110% ($5 premium)"),
              (hor, AQUA, "Polymarket YES Hormuz ($5)"),
              (usa, YELLOW, "Polymarket YES US military action ($5)")]
    for v, color, label in series:
        ax.plot(ts, v, color=color, linewidth=2, solid_capstyle="round", label=label)

    ax.axhline(0, color=BASE, linewidth=0.9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(BASE)
    ax.grid(True, axis="y", color=GRID, linewidth=0.7)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.set_ylabel("P&L (USD, per 100 USD of exposure)", color=INK2, fontsize=10)
    ax.set_title("June 2025 backtest: equal-premium crisis hedges, marked to market hourly",
                 color=INK, fontsize=12.5, loc="left", pad=12)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK2)

    cease = dt.datetime(2025, 6, 23, 22, tzinfo=dt.timezone.utc)
    ax.axvline(cease, color=BASE, linewidth=0.9, linestyle=(0, (3, 3)))
    ax.annotate("Ceasefire announced", xy=(cease, ax.get_ylim()[1]),
                xytext=(6, -12), textcoords="offset points",
                color=INK2, fontsize=8.5)

    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.text(0.01, -0.02, "Entry Jun 16 00:00 UTC. Digital priced Black-76 with OVX "
             "(free-data proxy for a call spread). Shaded: futures closed. "
             "Hedge P&L excludes execution costs.", color=MUTED, fontsize=8)

    out = os.path.join(EP, "backtest_jun2025.png")
    fig.savefig(out, bbox_inches="tight", facecolor=SURFACE)
    print("saved", out)


if __name__ == "__main__":
    main()
