"""
Root-cause analysis of the FreshCart D7 retention drop (pandas version of the SQL steps).

Outputs:
    reports/figures/*.png
    reports/findings.md   (all numbers in the README come from this file)

Run:  python src/analysis.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA, FIG = ROOT / "data", ROOT / "reports" / "figures"
RELEASE_420, RELEASE_421 = pd.Timestamp("2026-07-06"), pd.Timestamp("2026-07-23")
BEFORE = ("2026-06-08", "2026-07-05")     # 4 clean weeks
AFTER = ("2026-07-06", "2026-07-19")      # 2 incident weeks

plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.3, "font.size": 10})
BLUE, RED, GREY = "#2563eb", "#dc2626", "#9ca3af"


# --------------------------------------------------------------------------- data
def load_user_metrics() -> pd.DataFrame:
    """One row per user with funnel flags and D7 retention (days 7..13 after signup)."""
    users = pd.read_csv(DATA / "users.csv", parse_dates=["signup_ts"])
    events = pd.read_csv(DATA / "events.csv", parse_dates=["event_ts"])

    flags = (events[events.event_name != "session"]
             .assign(v=True)
             .pivot_table(index="user_id", columns="event_name", values="v", aggfunc="any"))

    s = events[events.event_name == "session"].merge(users[["user_id", "signup_ts"]], on="user_id")
    age = s.event_ts - s.signup_ts
    retained = s.loc[(age >= pd.Timedelta(days=7)) & (age < pd.Timedelta(days=14)), "user_id"].unique()

    df = users.merge(flags, left_on="user_id", right_index=True, how="left")
    for c in ["address_confirmed", "payment_added", "first_order"]:
        df[c] = df[c].fillna(False).astype(bool)
    df["retained_d7"] = df.user_id.isin(retained)
    df["cohort_week"] = df.signup_ts.dt.to_period("W-SUN").dt.start_time
    df["affected"] = (df.platform == "android") & (df.app_version == "4.2.0")
    return df


def period(df: pd.DataFrame, bounds: tuple[str, str]) -> pd.DataFrame:
    return df[(df.signup_ts >= bounds[0]) & (df.signup_ts < pd.Timestamp(bounds[1]) + pd.Timedelta(days=1))]


# --------------------------------------------------------------------------- stats
def two_prop_ztest(x1: int, n1: int, x2: int, n2: int, alpha: float = 0.05) -> dict:
    """Two-proportion z-test (pooled SE for the test, unpooled SE for the CI)."""
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    z = (p1 - p2) / np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    q = stats.norm.ppf(1 - alpha / 2)
    return {"p1": p1, "p2": p2, "diff": p1 - p2, "ci": (p1 - p2 - q * se, p1 - p2 + q * se),
            "z": z, "p_value": 2 * stats.norm.sf(abs(z))}


# --------------------------------------------------------------------------- decomposition
def bug_corrected(after: pd.DataFrame) -> pd.Series:
    """Counterfactual retention for affected users = retention of unaffected users
    in the same channel and period (controls for the channel mix)."""
    ctrl = after[~after.affected].groupby("channel").retained_d7.mean()
    expected = after.channel.map(ctrl)
    return np.where(after.affected, expected, after.retained_d7.astype(float))


def kitagawa(before: pd.DataFrame, after: pd.DataFrame, after_ret: np.ndarray, by: str) -> dict:
    """Split a change in an average into mix (share) and rate components."""
    b = before.groupby(by).agg(n=("user_id", "size"), r=("retained_d7", "mean"))
    a = after.assign(r=after_ret).groupby(by).agg(n=("user_id", "size"), r=("r", "mean"))
    t = b.join(a, lsuffix="_b", rsuffix="_a", how="outer").fillna(0)
    t["s_b"], t["s_a"] = t.n_b / t.n_b.sum(), t.n_a / t.n_a.sum()
    mix = ((t.s_a - t.s_b) * (t.r_a + t.r_b) / 2).sum()
    rate = ((t.r_a - t.r_b) * (t.s_a + t.s_b) / 2).sum()
    return {"mix": mix, "rate": rate, "table": t}


# --------------------------------------------------------------------------- charts
def chart_weekly(df: pd.DataFrame) -> None:
    w = df.groupby("cohort_week").agg(ret=("retained_d7", "mean"), n=("user_id", "size"))
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(w.index, w.ret * 100, marker="o", color=BLUE, lw=2)
    ax.axvline(RELEASE_420, color=RED, ls="--", lw=1)
    ax.text(RELEASE_420, ax.get_ylim()[1] * 0.98, " Android 4.2.0 +\n influencer campaign",
            color=RED, va="top", fontsize=9)
    ax.set_ylabel("D7 retention, %")
    ax.set_title("Weekly signup cohorts: D7 retention dropped ~7 pp")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "01_weekly_retention.png")
    plt.close(fig)


def chart_funnel(after: pd.DataFrame) -> None:
    g = (after.assign(seg=after.platform + " " + after.app_version)
         .groupby("seg")[["address_confirmed", "payment_added", "first_order"]].mean() * 100)
    g = g.loc[g.index.isin(["android 4.1.3", "android 4.2.0", "ios 4.2.0", "web web"])]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    x = np.arange(3)
    width = 0.2
    palette = {"android 4.1.3": BLUE, "android 4.2.0": RED, "ios 4.2.0": "#60a5fa", "web web": "#a5b4fc"}
    for i, (seg, row) in enumerate(g.iterrows()):
        ax.bar(x + (i - 1.5) * width, row.values, width, label=seg.replace("web web", "web"),
               color=palette[seg])
    ax.set_xticks(x, ["address confirmed", "payment added", "first order"])
    ax.set_ylabel("% of signups (cumulative)")
    ax.set_title("Onboarding funnel, incident weeks: Android 4.2.0 loses users at the address step")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "02_funnel_by_version.png")
    plt.close(fig)


def chart_daily(df: pd.DataFrame) -> None:
    d = df[(df.platform == "android") & (df.signup_ts >= "2026-06-22")]
    g = d.groupby([d.signup_ts.dt.date, "app_version"]).address_confirmed.agg(["mean", "size"])
    g = g[g["size"] >= 50].reset_index()
    fig, ax = plt.subplots(figsize=(8, 3.6))
    colors = {"4.1.3": BLUE, "4.2.0": RED, "4.2.1": "#16a34a"}
    for v, part in g.groupby("app_version"):
        ax.plot(pd.to_datetime(part.signup_ts), part["mean"] * 100, marker=".", label=v, color=colors[v])
    for t, lbl in [(RELEASE_420, "4.2.0 rollout"), (RELEASE_421, "4.2.1 hotfix")]:
        ax.axvline(t, color=GREY, ls="--", lw=1)
        ax.text(t, 40, " " + lbl, color="#4b5563", fontsize=8)
    ax.set_ylim(35, 95)
    ax.set_ylabel("signup → address, %")
    ax.set_title("Android, daily: step change exactly at the 4.2.0 release, recovery with 4.2.1")
    ax.legend(frameon=False, title="version")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "03_android_daily_address_rate.png")
    plt.close(fig)


def chart_waterfall(parts: dict[str, float]) -> None:
    labels = list(parts) + ["total"]
    vals = list(parts.values())
    total = sum(vals)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    cum = 0.0
    for i, v in enumerate(vals):
        ax.bar(i, v * 100, bottom=cum * 100, color=RED if v < 0 else "#16a34a")
        ax.text(i, (cum + v / 2) * 100, f"{v*100:+.1f}", ha="center", va="center",
                fontsize=9, color="white" if abs(v) > 0.006 else "black")
        cum += v
    ax.bar(len(vals), total * 100, color=GREY)
    ax.text(len(vals), total * 50, f"{total*100:+.1f}", ha="center", va="center", fontsize=9, color="white")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylabel("contribution, pp")
    ax.set_title("What explains the D7 retention change (before → incident weeks)")
    fig.tight_layout()
    fig.savefig(FIG / "04_decomposition_waterfall.png")
    plt.close(fig)


# --------------------------------------------------------------------------- main
def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    df = load_user_metrics()
    before, after = period(df, BEFORE), period(df, AFTER)

    r_b, r_a = before.retained_d7.mean(), after.retained_d7.mean()
    total_delta = r_a - r_b
    overall = two_prop_ztest(after.retained_d7.sum(), len(after), before.retained_d7.sum(), len(before))

    # 1) bug effect (rate effect inside Android 4.2.0, channel-adjusted)
    corrected = bug_corrected(after)
    bug_effect = r_a - corrected.mean()

    # 2) channel mix vs remaining rate change on bug-corrected data
    k = kitagawa(before, after, corrected, by="channel")

    # address step: affected vs unaffected Android in the same weeks
    a_and = after[after.platform == "android"]
    addr = two_prop_ztest(a_and[a_and.affected].address_confirmed.sum(), a_and.affected.sum(),
                          a_and[~a_and.affected].address_confirmed.sum(), (~a_and.affected).sum())
    ret_aff = two_prop_ztest(a_and[a_and.affected].retained_d7.sum(), a_and.affected.sum(),
                             a_and[~a_and.affected].retained_d7.sum(), (~a_and.affected).sum())

    # sizing: retained users lost per week because of the bug
    weekly_affected = after.affected.sum() / 2
    lost_per_week = -bug_effect * len(after) / 2

    chart_weekly(df)
    chart_funnel(after)
    chart_daily(df)
    chart_waterfall({"Android 4.2.0 bug": bug_effect,
                     "channel mix\n(influencer)": k["mix"],
                     "other\n(seasonality, noise)": k["rate"]})

    infl = k["table"].loc["influencer"]
    pp = lambda x: f"{x * 100:+.1f} pp"
    report = f"""# Findings (auto-generated by `src/analysis.py`)

Periods: before = {BEFORE[0]}..{BEFORE[1]} (n={len(before):,}), incident = {AFTER[0]}..{AFTER[1]} (n={len(after):,}).

| metric | value |
|---|---|
| D7 retention before | {r_b*100:.1f}% |
| D7 retention incident weeks | {r_a*100:.1f}% |
| change | {pp(total_delta)} (95% CI {overall['ci'][0]*100:+.1f} … {overall['ci'][1]*100:+.1f}, p={overall['p_value']:.1e}) |

## Decomposition of the change

| driver | contribution | share of drop |
|---|---|---|
| Android 4.2.0 onboarding bug (rate) | {pp(bug_effect)} | {bug_effect/total_delta:.0%} |
| Channel mix: influencer campaign | {pp(k['mix'])} | {k['mix']/total_delta:.0%} |
| Other (seasonality / noise) | {pp(k['rate'])} | {k['rate']/total_delta:.0%} |
| **Total** | **{pp(total_delta)}** | 100% |

Influencer share of signups: {infl.s_b:.1%} → {infl.s_a:.1%}; its D7 retention ≈ {infl.r_a:.1%}
vs {(after[after.channel!='influencer'].retained_d7.mean()):.1%} for other channels in the same weeks.

## Android 4.2.0 vs other Android versions (incident weeks)

| metric | 4.2.0 | other Android | diff (95% CI) |
|---|---|---|---|
| signup → address | {addr['p1']:.1%} | {addr['p2']:.1%} | {pp(addr['diff'])} ({addr['ci'][0]*100:+.1f} … {addr['ci'][1]*100:+.1f}) |
| D7 retention | {ret_aff['p1']:.1%} | {ret_aff['p2']:.1%} | {pp(ret_aff['diff'])} ({ret_aff['ci'][0]*100:+.1f} … {ret_aff['ci'][1]*100:+.1f}) |

Later funnel steps (address → payment → order) are unchanged, so the loss is isolated to one screen.

## Sizing
~{weekly_affected:,.0f} new users/week landed on Android 4.2.0; the bug cost
~{lost_per_week:,.0f} retained users per week.
"""
    (ROOT / "reports" / "findings.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
