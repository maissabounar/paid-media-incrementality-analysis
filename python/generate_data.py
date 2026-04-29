"""
generate_data.py
Generates a synthetic user-level dataset for the paid media incrementality case study.
Output: data/synthetic_data.csv

Each row is one user. Treated users saw at least one paid impression.
Control users visited the site but were not served a paid ad in the same window.

Retargeting audiences are seeded with high prior-purchase counts and organic session
activity to reproduce the selection bias the PSM is designed to correct.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(42)
Path("data").mkdir(exist_ok=True)

# ── Segment definitions ────────────────────────────────────────────────────────
# (channel, audience_type): (share, baseline_cvr, treated_cvr, avg_freq, cpm)
#
# baseline_cvr: CVR this audience achieves with zero ad exposure (organic intent)
# treated_cvr:  observed CVR when the ad is served (baseline + incremental lift)
#
# The gap between baseline and treated_cvr drives the incrementality result.
# Retargeting: small gap → low lift. Prospecting: large gap → high lift.
SEGMENTS = {
    ("tiktok",   "prospecting_broad_1824"):   (0.100, 0.018, 0.048,  4.2,  8.1),
    ("tiktok",   "prospecting_broad_2534"):   (0.070, 0.025, 0.059,  3.8,  8.4),
    ("meta",     "prospecting_lal_1pct"):     (0.125, 0.021, 0.055,  5.1,  9.2),
    ("meta",     "prospecting_lal_3_5pct"):   (0.075, 0.028, 0.069,  4.7,  8.8),
    ("meta",     "prospecting_broad"):        (0.060, 0.022, 0.048,  4.0,  7.5),
    ("youtube",  "prospecting_brand_safety"): (0.060, 0.032, 0.073,  3.5, 12.0),
    ("tiktok",   "retargeting"):              (0.070, 0.079, 0.100,  8.3,  9.5),
    ("meta",     "retargeting_warm"):         (0.135, 0.084, 0.104, 11.2, 10.1),
    ("meta",     "retargeting_hot"):          (0.105, 0.133, 0.150, 13.8, 11.5),
    ("youtube",  "retargeting"):              (0.100, 0.108, 0.118,  9.6, 10.8),
}

COUNTRIES     = ["FR", "GB", "DE"]
COUNTRY_W     = [0.35, 0.40, 0.25]
AGE_GROUPS    = ["18-24", "25-34", "35-44", "45+"]
AGE_W         = [0.20, 0.30, 0.28, 0.22]
DEVICES       = ["mobile", "desktop", "tablet"]
DEVICE_W      = [0.60, 0.35, 0.05]
LOYALTY_TIERS = ["none", "silver", "gold", "platinum"]
LOYALTY_W     = [0.55, 0.25, 0.15, 0.05]
CATEGORIES    = ["skincare", "makeup", "fragrance", "haircare"]


def make_features(n: int, intent: float = 0.0) -> pd.DataFrame:
    """
    intent=0.0 → prospecting profile: few prior purchases, low organic engagement
    intent=1.0 → retargeting profile: many purchases, high engagement, recent visit

    This gradient is what creates the selection bias the PSM corrects for.
    High-intent users are more likely to be targeted AND more likely to convert
    regardless of ad exposure — which is exactly why reported CPA misleads.
    """
    return pd.DataFrame({
        "n_prior_purchases":      np.random.negative_binomial(
                                      1 + intent * 4, 0.4, n).clip(0, 20),
        "n_organic_sessions_30d": np.random.poisson(
                                      1.5 + intent * 7, n).clip(0, 30),
        "days_since_last_visit":  np.random.exponential(
                                      22 - intent * 14, n).clip(1, 120).astype(int),
        "email_subscriber":       np.random.binomial(1, 0.30 + intent * 0.35, n),
        "country":                np.random.choice(COUNTRIES, n, p=COUNTRY_W),
        "age_group":              np.random.choice(AGE_GROUPS,    n, p=AGE_W),
        "device_type":            np.random.choice(DEVICES,       n, p=DEVICE_W),
        "loyalty_tier":           np.random.choice(LOYALTY_TIERS, n, p=LOYALTY_W),
        "category_affinity":      np.random.choice(CATEGORIES,    n),
    })


# ── Treated users (exposed to at least one paid impression) ────────────────────
N_TREATED   = 13_000
seg_keys    = list(SEGMENTS.keys())
seg_shares  = np.array([SEGMENTS[s][0] for s in seg_keys])
seg_assign  = np.random.choice(
    len(seg_keys), N_TREATED, p=seg_shares / seg_shares.sum()
)

treated_parts = []
for i, (ch, at) in enumerate(seg_keys):
    _, base_cvr, treat_cvr, avg_freq, cpm = SEGMENTS[(ch, at)]
    n = (seg_assign == i).sum()
    if n == 0:
        continue

    # Retargeting users look like people who were already going to buy.
    # Prospecting users have low intent scores before any ad exposure.
    intent = 0.80 if "retargeting" in at else 0.05
    feats  = make_features(n, intent=intent)

    freq  = np.random.normal(avg_freq, avg_freq * 0.4, n).clip(1, 60).astype(int)
    spend = (freq * cpm / 1000 * np.random.uniform(0.85, 1.15, n)).round(2)

    feats["user_id"]       = [f"T{i:02d}_{j:05d}" for j in range(n)]
    feats["treatment"]     = 1
    feats["channel"]       = ch
    feats["audience_type"] = at
    feats["frequency"]     = freq
    feats["spend_eur"]     = spend
    feats["converted"]     = np.random.binomial(1, treat_cvr, n)
    treated_parts.append(feats)

treated_df = pd.concat(treated_parts, ignore_index=True)

# ── Control users (active on site, no paid impressions) ───────────────────────
# Three intent bands to give the matching algorithm enough coverage:
# most control users are low-intent, but some moderate and high-intent
# users exist who happened not to be served an ad this window.
N_CONTROL   = 7_000
ctrl_parts  = []
for intent_val, share, base_cvr in [
    (0.00, 0.60, 0.015),
    (0.35, 0.30, 0.045),
    (0.75, 0.10, 0.095),
]:
    n     = int(N_CONTROL * share)
    feats = make_features(n, intent=intent_val)
    feats["converted"] = np.random.binomial(1, base_cvr, n)
    ctrl_parts.append(feats)

ctrl_df = pd.concat(ctrl_parts, ignore_index=True)
ctrl_df["user_id"]       = [f"C_{j:05d}" for j in range(len(ctrl_df))]
ctrl_df["treatment"]     = 0
ctrl_df["channel"]       = None
ctrl_df["audience_type"] = None
ctrl_df["frequency"]     = 0
ctrl_df["spend_eur"]     = 0.0

# ── Combine & save ─────────────────────────────────────────────────────────────
COLS = [
    "user_id", "treatment", "channel", "audience_type",
    "country", "age_group", "device_type", "email_subscriber",
    "n_prior_purchases", "n_organic_sessions_30d", "days_since_last_visit",
    "loyalty_tier", "category_affinity", "frequency", "spend_eur", "converted",
]
out = (
    pd.concat([treated_df, ctrl_df], ignore_index=True)
    .sample(frac=1, random_state=42)
    .reset_index(drop=True)
)
out[COLS].to_csv("data/synthetic_data.csv", index=False)

print(f"Saved {len(out):,} users → data/synthetic_data.csv")
print(f"  Treated CVR : {treated_df['converted'].mean():.1%}")
print(f"  Control CVR : {ctrl_df['converted'].mean():.1%}")
