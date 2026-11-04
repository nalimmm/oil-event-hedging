"""Chart of the June 2025 episode: Brent vs prediction market odds.

Two stacked panels on a shared time axis (one y-scale each, never dual-axis):
top Brent hourly, bottom event probabilities (10-minute). Weekend futures
closures are shaded; key events are annotated. Colors follow the validated
reference palette (light mode). Output: data/episode_jun2025/episode_jun2025.png
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

# reference palette, light mode
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"


def read(path, col):
    ts, vs = [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            ts.append(dt.datetime.fromtimestamp(int(row["ts"]), dt.timezone.utc))
            vs.append(float(row[col]))
    return ts, vs


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(BASE)
    ax.grid(True, axis="y", color=GRID, linewidth=0.7)
    ax.tick_params(colors=MUTED, labelsize=9)


def main():
    bt, bv = read(os.path.join(EP, "brent_hourly.csv"), "close")
    series = {}
    for name in ("hormuz", "ceasefire", "us_war"):
        series[name] = read(os.path.join(EP, f"pm_{name}.csv"), "prob")

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 6.6), sharex=True, dpi=160,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.12})
    fig.patch.set_facecolor(SURFACE)

    # --- shaded futures-closed weekends
    weekends = [
        (dt.datetime(2025, 6, 13, 21, tzinfo=dt.timezone.utc),
         dt.datetime(2025, 6, 15, 22, tzinfo=dt.timezone.utc)),
        (dt.datetime(2025, 6, 20, 21, tzinfo=dt.timezone.utc),
         dt.datetime(2025, 6, 22, 22, tzinfo=dt.timezone.utc)),
        (dt.datetime(2025, 6, 27, 21, tzinfo=dt.timezone.utc),
         dt.datetime(2025, 6, 29, 22, tzinfo=dt.timezone.utc)),
    ]
    for ax in (ax1, ax2):
        for a, b in weekends:
            ax.axvspan(a, b, color=GRID, alpha=0.45, linewidth=0)

    # --- top: Brent
    ax1.plot(bt, bv, color=BLUE, linewidth=2, solid_capstyle="round")
    style(ax1)
    ax1.set_ylabel("Brent ($/bbl)", color=INK2, fontsize=10)
    ax1.set_title("June 2025 Israel-Iran war: Brent vs prediction market odds",
                  color=INK, fontsize=13, loc="left", pad=12)

    # --- bottom: probabilities
    specs = [("hormuz", ORANGE, "Hormuz closed before July"),
             ("ceasefire", AQUA, "Ceasefire before July"),
             ("us_war", YELLOW, "US declares war")]
    for name, color, label in specs:
        t, v = series[name]
        ax2.plot(t, v, color=color, linewidth=2, solid_capstyle="round", label=label)
    style(ax2)
    ax2.set_ylabel("Probability (Polymarket)", color=INK2, fontsize=10)
    ax2.set_ylim(-0.03, 1.03)
    ax2.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK2)

    # --- event annotations on the top panel
    # (time, label, x-offset pt, y-offset pt, ha)
    events = [
        (dt.datetime(2025, 6, 13, 0, 30, tzinfo=dt.timezone.utc),
         "Israel strikes Iran", 4, 16, "left"),
        (dt.datetime(2025, 6, 21, 23, 30, tzinfo=dt.timezone.utc),
         "US strikes Fordow (futures closed)", -4, 16, "right"),
        (dt.datetime(2025, 6, 23, 17, 0, tzinfo=dt.timezone.utc),
         "Iran hits Al Udeid", 4, 2, "left"),
        (dt.datetime(2025, 6, 23, 22, 30, tzinfo=dt.timezone.utc),
         "Ceasefire announced", 10, 16, "left"),
    ]
    ymin, ymax = min(bv), max(bv)
    ax1.set_ylim(ymin - 2, ymax + 7)
    for t, label, dx, dy, ha in events:
        for ax in (ax1, ax2):
            ax.axvline(t, color=BASE, linewidth=0.9, linestyle=(0, (3, 3)))
        ax1.annotate(label, xy=(t, ymax + 0.5), xytext=(dx, dy),
                     textcoords="offset points", color=INK2, fontsize=8.5, ha=ha)

    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax2.set_xlim(dt.datetime(2025, 6, 11, tzinfo=dt.timezone.utc),
                 dt.datetime(2025, 7, 3, tzinfo=dt.timezone.utc))
    fig.text(0.01, 0.01, "Shaded: CME/ICE futures closed (weekends). "
             "Sources: Polymarket CLOB, Yahoo Finance. All times UTC.",
             color=MUTED, fontsize=8)

    out = os.path.join(EP, "episode_jun2025.png")
    fig.savefig(out, bbox_inches="tight", facecolor=SURFACE)
    print("saved", out)


if __name__ == "__main__":
    main()
