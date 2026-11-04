"""June 2025 Israel-Iran war: align prediction market odds with oil prices.

Reads data/episode_jun2025/ (built by the download step), writes
merged_hourly.csv there, and prints the chronology, lead/lag
cross-correlations, conditional impact regressions and the weekend-gap
analysis around the US strike on Fordow (futures closed, Polymarket open).
"""
import csv
import datetime as dt
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
EP = os.path.join(os.path.dirname(HERE), "data", "episode_jun2025")

PM = ["hormuz", "ceasefire", "iran_strike_fri", "us_action_aug", "us_war"]


def read_ts_csv(path, val):
    out = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            out[int(row["ts"])] = float(row[val])
    return out


def hourly(series):
    """Last observation per hour bucket."""
    out = {}
    for t in sorted(series):
        out[t // 3600 * 3600] = series[t]
    return out


def fmt(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")


def corr(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    sx = sum((a - mx) ** 2 for a in xs) ** 0.5
    sy = sum((b - my) ** 2 for b in ys) ** 0.5
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (sx * sy)


def changes(h, grid):
    """Series of (t, delta) on consecutive grid hours where both ends exist."""
    out = {}
    for i in range(1, len(grid)):
        a, b = grid[i - 1], grid[i]
        if a in h and b in h:
            out[b] = h[b] - h[a]
    return out


def main():
    pm = {n: hourly(read_ts_csv(os.path.join(EP, f"pm_{n}.csv"), "prob")) for n in PM}
    brent = hourly(read_ts_csv(os.path.join(EP, "brent_hourly.csv"), "close"))
    wti = hourly(read_ts_csv(os.path.join(EP, "wti_hourly.csv"), "close"))

    grid = sorted(set().union(brent, wti, *pm.values()))
    with open(os.path.join(EP, "merged_hourly.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "utc", "brent", "wti"] + PM)
        for t in grid:
            w.writerow([t, fmt(t), brent.get(t), wti.get(t)]
                       + [pm[n].get(t) for n in PM])
    print(f"merged_hourly.csv: {len(grid)} hours\n")

    # --- chronology: largest hourly PM moves and Brent moves
    print("== Largest hourly swings ==")
    for n in PM:
        ch = changes(pm[n], grid)
        if not ch:
            continue
        top = sorted(ch.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        tops = ", ".join(f"{fmt(t)} {d:+.2f} -> {pm[n][t]:.2f}" for t, d in top)
        print(f"  {n:16} {tops}")
    rb = changes(brent, grid)
    top = sorted(rb.items(), key=lambda kv: abs(kv[1] / brent[kv[0]]), reverse=True)[:5]
    print("  brent          ", ", ".join(
        f"{fmt(t)} {d / (brent[t] - d) * 100:+.1f}%" for t, d in top))

    # --- lead/lag cross-correlation: dP(hormuz & us_war) vs Brent returns
    print("\n== Lead/lag: corr( dP at t-k , Brent return at t ), k in hours ==")
    bret = {t: d / (brent[t] - d) for t, d in rb.items()}
    for n in ["hormuz", "us_war", "ceasefire"]:
        ch = changes(pm[n], grid)
        line = []
        for k in range(-6, 7):
            xs, ys = [], []
            for t in bret:
                tk = t - k * 3600
                if tk in ch:
                    xs.append(ch[tk])
                    ys.append(bret[t])
            line.append(f"k={k:+d}:{corr(xs, ys):+.2f}(n={len(xs)})" if len(xs) > 20
                        else f"k={k:+d}: -")
        print(f"  {n:10} " + " ".join(line))

    # --- conditional impact: OLS slope of Brent hourly return on dP
    print("\n== Conditional impact (same hour): Brent % per +10pp of prob ==")
    for n in ["hormuz", "us_war", "ceasefire"]:
        ch = changes(pm[n], grid)
        xs = [ch[t] for t in bret if t in ch]
        ys = [bret[t] * 100 for t in bret if t in ch]
        if len(xs) > 20:
            mx, my = st.mean(xs), st.mean(ys)
            beta = (sum((a - mx) * (b - my) for a, b in zip(xs, ys))
                    / sum((a - mx) ** 2 for a in xs))
            print(f"  {n:10} beta = {beta * 0.10:+.2f}% per +10pp  "
                  f"(corr {corr(xs, ys):+.2f}, n={len(xs)})")

    # --- the weekend: Fordow strike while futures were closed
    print("\n== Weekend of June 21-22 (US strike on Fordow; futures closed) ==")
    fri_close_t = max(t for t in brent if t <= 1750455000)   # ~Fri Jun 20 21:30 UTC
    sun_open_t = min(t for t in brent if t > 1750455000)
    print(f"  Brent last trade  {fmt(fri_close_t)}  {brent[fri_close_t]:.2f}")
    print(f"  Brent next trade  {fmt(sun_open_t)}  {brent[sun_open_t]:.2f}  "
          f"gap {(brent[sun_open_t] / brent[fri_close_t] - 1) * 100:+.1f}%")
    for n in ["hormuz", "us_war", "ceasefire"]:
        h = pm[n]
        inwin = [t for t in h if fri_close_t <= t <= sun_open_t]
        if len(inwin) > 2:
            t0, t1 = min(inwin), max(inwin)
            path = [h[t] for t in sorted(inwin)]
            print(f"  {n:10} traded {len(inwin)} hrs while futures closed: "
                  f"{h[t0]:.2f} -> {h[t1]:.2f} (min {min(path):.2f}, max {max(path):.2f})")

    # --- ceasefire night June 23: who moved first, hour by hour
    print("\n== June 23, hour by hour (Iran strikes Qatar ~17h, Trump announces "
          "ceasefire ~22h UTC) ==")
    for t in [x for x in grid if 1750633200 <= x <= 1750734000]:
        row = f"  {fmt(t)}  brent {brent.get(t, float('nan')):7.2f}  "
        row += "  ".join(f"{n} {pm[n].get(t, float('nan')):5.2f}"
                         for n in ["hormuz", "ceasefire", "us_war"])
        print(row)


if __name__ == "__main__":
    main()
