"""Hedging backtest on the June 2025 episode.

A consumer (airline-type) holds $100 of short-crude exposure: it loses 1% of
notional per 1% Brent rally. On June 16, 00:00 UTC (first hour both Polymarket
war markets trade), it buys crisis protection and holds to June 30, with an
alternative exit at the pre-ceasefire Brent peak. Four instruments, equal
premium spend:

  A. digital call on Brent, strike 110% of entry spot, expiry June 30,
     priced hourly with Black-76 (sigma = OVX, linearly stepped daily);
     the free-data proxy for an OTM call spread
  B. Polymarket YES "Iran closes the Strait of Hormuz before July"
  C. Polymarket YES "US military action against Iran before August"
     (broad resolution criterion; resolved YES at Fordow)
  D. Polymarket YES "US officially declares war on Iran before July"
     (narrow criterion; resolved NO through actual strikes)

Also: in-sample minimum-variance dynamic hedge ratios and variance reduction,
and the weekend-availability ledger. Reads data/episode_jun2025/, writes
hedge_paths.csv next to it and prints the results tables.
"""
import csv
import datetime as dt
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EP = os.path.join(os.path.dirname(HERE), "data", "episode_jun2025")

ENTRY = int(dt.datetime(2025, 6, 16, 0, tzinfo=dt.timezone.utc).timestamp())
EXPIRY = int(dt.datetime(2025, 6, 30, 0, tzinfo=dt.timezone.utc).timestamp())
NOTIONAL = 100.0
PREMIUM = 5.0          # equal spend on every hedge, $ per $100 of exposure
STRIKE_MULT = 1.10


def read_ts(path, col):
    out = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            out[int(row["ts"])] = float(row[col])
    return out


def hourly(series):
    out = {}
    for t in sorted(series):
        out[t // 3600 * 3600] = series[t]
    return out


def ffill(series, grid):
    out, last = {}, None
    for t in grid:
        if t in series:
            last = series[t]
        if last is not None:
            out[t] = last
    return out


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def digital_price(F, K, sigma, T):
    """Black-76 cash-or-nothing call, r=0, unit payout."""
    if T <= 0:
        return 1.0 if F > K else 0.0
    d2 = (math.log(F / K) - 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    return norm_cdf(d2)


def fmt(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")


def main():
    brent = hourly(read_ts(os.path.join(EP, "brent_hourly.csv"), "close"))
    pm = {n: hourly(read_ts(os.path.join(EP, f"pm_{n}.csv"), "prob"))
          for n in ("hormuz", "us_action_aug", "us_war")}
    ovx = {}
    with open(os.path.join(EP, "ovx_daily.csv")) as f:
        for row in csv.DictReader(f):
            d = dt.datetime.fromisoformat(row["date"]).replace(tzinfo=dt.timezone.utc)
            ovx[int(d.timestamp()) // 86400] = float(row["ovx"]) / 100.0

    grid = [t for t in sorted(brent) if ENTRY <= t <= EXPIRY]
    B = {t: brent[t] for t in grid}
    B0 = B[grid[0]]
    K = STRIKE_MULT * B0

    def sigma_at(t):
        day = t // 86400
        for back in range(0, 6):
            if day - back in ovx:
                return ovx[day - back]
        return 0.40

    # entry prices
    p0 = {}
    p0["digital"] = digital_price(B0, K, sigma_at(grid[0]), (EXPIRY - grid[0]) / 86400 / 365)
    pm_f = {n: ffill(pm[n], grid) for n in pm}
    for n in pm:
        p0[n] = pm_f[n][grid[0]]

    units = {k: PREMIUM / v for k, v in p0.items()}   # payout units bought for $5

    print(f"Entry {fmt(grid[0])} UTC | Brent {B0:.2f} | strike {K:.2f} | "
          f"OVX {sigma_at(grid[0]) * 100:.0f}%")
    print("Entry prices per $1 payout: "
          + ", ".join(f"{k} {v:.3f}" for k, v in p0.items()))
    print("Units bought for $" + str(PREMIUM) + ": "
          + ", ".join(f"{k} {units[k]:.1f}" for k in units) + "\n")

    # hourly mark-to-market of each hedge, and of the exposure
    rows = []
    for t in grid:
        T = max((EXPIRY - t) / 86400 / 365, 0.0)
        vals = {
            "digital": units["digital"] * digital_price(B[t], K, sigma_at(t), T),
            "hormuz": units["hormuz"] * pm_f["hormuz"][t],
            "us_action_aug": units["us_action_aug"] * min(pm_f["us_action_aug"][t], 1.0),
            "us_war": units["us_war"] * pm_f["us_war"][t],
        }
        exposure = -NOTIONAL * (B[t] / B0 - 1.0)
        rows.append({"ts": t, "utc": fmt(t), "brent": B[t], "exposure_pnl": round(exposure, 2),
                     **{k: round(v, 2) for k, v in vals.items()}})

    with open(os.path.join(EP, "hedge_paths.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # resolution values
    final = {"digital": 1.0 if max(B.values()) and B[grid[-1]] > K else 0.0,
             "hormuz": 0.0, "us_action_aug": 1.0, "us_war": 0.0}

    # scenario table: peak-fear exit vs hold to resolution
    peak_t = max(grid, key=lambda t: B[t])
    peak_row = next(r for r in rows if r["ts"] == peak_t)
    print(f"== Exit at Brent peak ({fmt(peak_t)}, Brent {B[peak_t]:.2f}; "
          f"exposure P&L {peak_row['exposure_pnl']:+.2f}) ==")
    for k in ("digital", "hormuz", "us_action_aug", "us_war"):
        v = peak_row[k]
        print(f"  {k:14} value {v:6.2f}  P&L {v - PREMIUM:+6.2f}  "
              f"({(v - PREMIUM) / PREMIUM * 100:+6.0f}%)")

    print(f"\n== Hold to resolution (June 30; exposure P&L "
          f"{rows[-1]['exposure_pnl']:+.2f}) ==")
    for k in ("digital", "hormuz", "us_action_aug", "us_war"):
        v = units[k] * final[k]
        print(f"  {k:14} payout {v:6.2f}  P&L {v - PREMIUM:+6.2f}  "
              f"({(v - PREMIUM) / PREMIUM * 100:+6.0f}%)")

    # minimum-variance dynamic hedge (in-sample, hourly changes)
    print("\n== Min-variance dynamic hedge, hourly (in-sample) ==")
    dE = [rows[i]["exposure_pnl"] - rows[i - 1]["exposure_pnl"] for i in range(1, len(rows))]
    import statistics as st
    for k in ("digital", "hormuz", "us_action_aug"):
        dH = [rows[i][k] - rows[i - 1][k] for i in range(1, len(rows))]
        if st.pstdev(dH) == 0:
            continue
        cov = sum((a - st.mean(dE)) * (b - st.mean(dH)) for a, b in zip(dE, dH)) / len(dE)
        h = -cov / st.pvariance(dH)
        resid = [a + h * b for a, b in zip(dE, dH)]
        vr = 1 - st.pvariance(resid) / st.pvariance(dE)
        print(f"  {k:14} hedge ratio {h:+.2f} units  variance reduction {vr * 100:5.1f}%")

    # weekend availability ledger
    print("\n== Fordow weekend (futures closed Fri 20 Jun 21:00 -> Sun 22 Jun 22:00 UTC) ==")
    for k in ("hormuz", "us_action_aug"):
        s = pm[k]
        w = [t for t in s if 1750453200 <= t <= 1750629600]
        if w:
            t0, t1 = min(w), max(w)
            print(f"  {k:14} tradable: {len(w)} hourly prints, "
                  f"{s[t0]:.2f} ({fmt(t0)}) -> {s[t1]:.2f} ({fmt(t1)})")
    print("  digital        NOT tradable (exchange closed)")


if __name__ == "__main__":
    main()
