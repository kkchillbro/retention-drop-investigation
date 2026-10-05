"""
Synthetic event data for a fictional grocery-delivery app "FreshCart".

The generator plants two root causes behind a D7 retention drop, so the
analysis can be checked against a known ground truth:

1. Rate effect: Android release 4.2.0 (rolled out from 2026-07-06) breaks the
   `address_confirmed` onboarding step. Fixed in 4.2.1 (from 2026-07-23).
2. Mix effect: an influencer campaign launched the same week brings a large
   share of low-intent users.

Everything is seeded and reproducible. Run:
    python src/generate_data.py --users 60000 --seed 42
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

START = pd.Timestamp("2026-06-01")          # Monday, first signup week
N_WEEKS = 8
RELEASE_420 = pd.Timestamp("2026-07-06")    # buggy Android release
RELEASE_421 = pd.Timestamp("2026-07-23")    # hotfix

CHANNELS = ["organic", "paid_search", "paid_social", "referral", "influencer"]
# Base probability that a user who placed a first order is active on days 7-13
RET_IF_ORDERED = {"organic": 0.58, "paid_search": 0.48, "paid_social": 0.40,
                  "referral": 0.62, "influencer": 0.27}
RET_IF_NOT_ORDERED = 0.07


def _channel_probs(week_start: pd.Timestamp) -> np.ndarray:
    """Acquisition mix. The influencer campaign starts on the release week."""
    if week_start >= RELEASE_420:
        return np.array([0.30, 0.20, 0.16, 0.08, 0.26])
    return np.array([0.40, 0.27, 0.22, 0.10, 0.01])


def _android_version(signup_ts: pd.Series, rng: np.random.Generator) -> np.ndarray:
    """Gradual rollout of 4.2.0, then the 4.2.1 hotfix."""
    days_since_420 = (signup_ts - RELEASE_420).dt.days.to_numpy()
    days_since_421 = (signup_ts - RELEASE_421).dt.days.to_numpy()
    share_420 = np.clip(0.35 + 0.12 * days_since_420, 0, 0.97)
    share_421 = np.clip(0.30 + 0.15 * days_since_421, 0, 0.95)
    u = rng.random(len(signup_ts))
    version = np.where(u < share_420, "4.2.0", "4.1.3")
    version = np.where((days_since_421 >= 0) & (rng.random(len(signup_ts)) < share_421),
                       "4.2.1", version)
    version = np.where(days_since_420 < 0, "4.1.3", version)
    return version


def generate(n_users: int = 60_000, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    # --- users -------------------------------------------------------------
    # slight weekly growth in signups
    week_weights = np.linspace(1.0, 1.25, N_WEEKS)
    week_idx = rng.choice(N_WEEKS, size=n_users, p=week_weights / week_weights.sum())
    signup_ts = (START + pd.to_timedelta(week_idx * 7, "D")
                 + pd.to_timedelta(rng.integers(0, 7 * 24 * 3600, n_users), "s"))
    signup_ts = pd.Series(signup_ts).sort_values().reset_index(drop=True)
    week_start = signup_ts.dt.normalize() - pd.to_timedelta(signup_ts.dt.weekday, "D")

    channel = np.empty(n_users, dtype=object)
    for ws in week_start.unique():
        m = (week_start == ws).to_numpy()
        channel[m] = rng.choice(CHANNELS, size=m.sum(), p=_channel_probs(ws))

    platform = rng.choice(["ios", "android", "web"], size=n_users, p=[0.44, 0.50, 0.06])
    app_version = np.where(platform == "ios", "4.2.0",
                           np.where(platform == "web", "web", "4.1.3")).astype(object)
    is_android = platform == "android"
    app_version[is_android] = _android_version(signup_ts[is_android], rng)

    city = rng.choice(["Berlin", "Warsaw", "Prague", "Vienna", "Lisbon"],
                      size=n_users, p=[0.32, 0.24, 0.16, 0.15, 0.13])

    users = pd.DataFrame({
        "user_id": np.arange(1, n_users + 1),
        "signup_ts": signup_ts,
        "platform": platform,
        "app_version": app_version,
        "channel": channel,
        "city": city,
    })

    # --- onboarding funnel -------------------------------------------------
    p_address = np.full(n_users, 0.86)
    p_address[channel == "influencer"] = 0.80
    p_address[app_version == "4.2.0"] = np.where(platform[app_version == "4.2.0"] == "android",
                                                 0.52, 0.86)
    p_payment = np.where(channel == "influencer", 0.62, 0.76)
    p_order = np.where(channel == "influencer", 0.70, 0.81)

    address = rng.random(n_users) < p_address
    payment = address & (rng.random(n_users) < p_payment)
    order = payment & (rng.random(n_users) < p_order)

    # --- retention ---------------------------------------------------------
    base = np.array([RET_IF_ORDERED[c] for c in channel])
    seasonal = -0.004 * week_idx                      # mild summer decay
    p_ret = np.where(order, base + seasonal, RET_IF_NOT_ORDERED)
    retained_w2 = rng.random(n_users) < np.clip(p_ret, 0, 1)

    # --- events ------------------------------------------------------------
    rows = []
    ts0 = users["signup_ts"]

    def add(mask, name, delay_s_low, delay_s_high):
        idx = np.flatnonzero(mask)
        delay = pd.to_timedelta(rng.integers(delay_s_low, delay_s_high, len(idx)), "s")
        rows.append(pd.DataFrame({"user_id": users["user_id"].to_numpy()[idx],
                                  "event_ts": ts0.to_numpy()[idx] + delay,
                                  "event_name": name}))

    add(np.ones(n_users, bool), "signup", 0, 1)
    add(address, "address_confirmed", 30, 600)
    add(payment, "payment_added", 600, 3600)
    add(order, "first_order", 3600, 2 * 24 * 3600)

    # sessions: days 1-6 (early engagement), days 7-13 (retention window), 14-27
    p_early = np.where(order, 0.55, 0.15)
    for day in range(1, 28):
        if day <= 6:
            p = p_early * (0.9 ** day)
        elif day <= 13:
            # retained users are active on ~2-3 days of week 2, at least one guaranteed below
            p = np.where(retained_w2, 0.35, 0.0)
        else:
            p = np.where(retained_w2, 0.30 * 0.95 ** (day - 14), 0.01)
        active = rng.random(n_users) < p
        add(active, "session", day * 86400, day * 86400 + 86399)

    # guarantee that every retained user has >=1 session in days 7-13
    guaranteed_day = rng.integers(7, 14, n_users)
    idx = np.flatnonzero(retained_w2)
    rows.append(pd.DataFrame({
        "user_id": users["user_id"].to_numpy()[idx],
        "event_ts": ts0.to_numpy()[idx] + pd.to_timedelta(
            guaranteed_day[idx] * 86400 + rng.integers(0, 86399, len(idx)), "s"),
        "event_name": "session"}))

    events = (pd.concat(rows, ignore_index=True)
              .drop_duplicates()
              .sort_values(["event_ts", "user_id"])
              .reset_index(drop=True))
    events.insert(0, "event_id", np.arange(1, len(events) + 1))
    events["event_ts"] = events["event_ts"].dt.floor("s")
    users["signup_ts"] = users["signup_ts"].dt.floor("s")
    return users, events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=60_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()

    users, events = generate(args.users, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    users.to_csv(args.out / "users.csv", index=False)
    events.to_csv(args.out / "events.csv", index=False)
    print(f"users: {len(users):,}  events: {len(events):,}  -> {args.out}")


if __name__ == "__main__":
    main()
