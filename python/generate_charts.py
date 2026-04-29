"""
generate_charts.py
Loads the synthetic dataset and produces all 4 charts for the case study.

Chart 1 is computed directly from the synthetic data — it illustrates
how PSM balances the treated and control groups before drawing any conclusions.

Charts 2–4 use the final segment-level numbers from the full 340K-user analysis.
These represent the output of the analysis described in the README, not
recomputed values from the smaller synthetic sample.

Output: images/chart_1_propensity.png through chart_4_waterfall.png
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from pathlib import Path

np.random.seed(42)
Path("images").mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family":        "sans-serif",
    "font.size":          10,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.grid":          False,
})

BLUE  = "#457B9D"
RED   = "#E63946"
GREEN = "#4CAF50"

# ── Load & encode ──────────────────────────────────────────────────────────────
df = pd.read_csv("data/synthetic_data.csv")
print(f"Loaded {len(df):,} users | {df['treatment'].mean():.1%} treated")

for col in ["country", "age_group", "device_type", "loyalty_tier", "category_affinity"]:
    le = LabelEncoder()
    df[col + "_enc"] = le.fit_transform(df[col].fillna("unknown"))

FEATURES = [
    "n_prior_purchases", "n_organic_sessions_30d", "days_since_last_visit",
    "email_subscriber",
    "country_enc", "age_group_enc", "device_type_enc", "loyalty_tier_enc",
]

# ── Propensity model ───────────────────────────────────────────────────────────
# Predict the probability each user was targeted by paid media.
# High score = platform would have targeted this user (they look "in-market").
model = LogisticRegression(max_iter=500, C=1.0, random_state=42)
model.fit(df[FEATURES].fillna(0), df["treatment"])
ps           = np.clip(model.predict_proba(df[FEATURES].fillna(0))[:, 1], 1e-6, 1 - 1e-6)
df["ps"]     = ps
df["logit_ps"] = np.log(ps / (1 - ps))

treated = df[df["treatment"] == 1].reset_index(drop=True)
control = df[df["treatment"] == 0].reset_index(drop=True)

# ── 1:1 nearest-neighbour matching ────────────────────────────────────────────
# Uses a sort + binary search approach for speed (O(n log n) instead of O(n²)).
# For each treated user, find the closest unused control user by propensity score.
CALIPER   = 0.10   # max allowed distance in logit(ps) units
N_SAMPLE  = 2_500  # use a subsample to keep runtime under a few seconds

t_sample  = treated.sample(N_SAMPLE, random_state=42).reset_index(drop=True)
c_sort_ix = np.argsort(control["logit_ps"].values)
c_sorted  = control["logit_ps"].values[c_sort_ix]
c_ps_sorted = control["ps"].values[c_sort_ix]
c_used    = np.zeros(len(c_sorted), dtype=bool)

matched_t_ps, matched_c_ps = [], []

for t_val, t_ps in zip(t_sample["logit_ps"].values, t_sample["ps"].values):
    j = int(np.searchsorted(c_sorted, t_val))
    best_j, best_dist = None, np.inf
    for candidate in range(max(0, j - 3), min(len(c_sorted), j + 4)):
        if not c_used[candidate]:
            d = abs(c_sorted[candidate] - t_val)
            if d < best_dist:
                best_dist, best_j = d, candidate
    if best_j is not None and best_dist <= CALIPER:
        matched_t_ps.append(t_ps)
        matched_c_ps.append(c_ps_sorted[best_j])
        c_used[best_j] = True

print(f"Matched {len(matched_t_ps):,} / {N_SAMPLE:,} sampled treated users")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 1 — Propensity score distribution before and after matching
#
# Before: treated and control look different (platforms target high-intent users).
# After:  matched pairs overlap — the groups are now comparable.
# The overlap is what makes the causal comparison valid.
# ─────────────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=False)

pairs = [
    (treated["ps"].values,   control["ps"].values,          "Before matching"),
    (np.array(matched_t_ps), np.array(matched_c_ps),        "After matching"),
]
for ax, (t_ps, c_ps, title) in zip(axes, pairs):
    ax.hist(t_ps, bins=35, alpha=0.55, color=RED,  density=True, label="Treated")
    ax.hist(c_ps, bins=35, alpha=0.55, color=BLUE, density=True, label="Control")
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Propensity score")
    ax.set_ylabel("Density")
    ax.legend(frameon=False, fontsize=9)

axes[0].set_title("Before matching\n(groups are different)", fontsize=11, fontweight="bold")
axes[1].set_title("After matching\n(groups are comparable)", fontsize=11, fontweight="bold")

fig.suptitle(
    "Common support check — matching makes the comparison fair",
    fontsize=12, fontweight="bold", y=1.02,
)
plt.tight_layout()
plt.savefig("images/chart_1_propensity.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved chart_1_propensity.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 2 — Reported CPA vs Incremental CPA (bubble chart)
#
# This is the core slide. Audiences in the bottom-left look efficient in the
# dashboard (low reported CPA). The same audiences sit in the top-right once
# measured correctly (high incremental CPA). The ranking flips entirely.
# ─────────────────────────────────────────────────────────────────────────────
segs = pd.DataFrame([
    {"label": "TikTok Broad 18–24",   "spend": 683_000, "rep_cpa":  85, "inc_cpa":  137, "lift": 0.62},
    {"label": "Meta LAL 1%",           "spend": 813_000, "rep_cpa":  92, "inc_cpa":  151, "lift": 0.61},
    {"label": "Meta LAL 3–5%",         "spend": 488_000, "rep_cpa": 105, "inc_cpa":  178, "lift": 0.59},
    {"label": "TikTok Broad 25–34",    "spend": 455_000, "rep_cpa":  98, "inc_cpa":  172, "lift": 0.57},
    {"label": "TikTok Retargeting",    "spend": 455_000, "rep_cpa":  72, "inc_cpa":  343, "lift": 0.21},
    {"label": "Meta Retarg. Warm",     "spend": 878_000, "rep_cpa":  90, "inc_cpa":  474, "lift": 0.19},
    {"label": "Meta Retarg. Hot",      "spend": 683_000, "rep_cpa":  55, "inc_cpa":  500, "lift": 0.11},
    {"label": "YouTube Retargeting",   "spend": 650_000, "rep_cpa":  75, "inc_cpa":  833, "lift": 0.09},
])

fig, ax = plt.subplots(figsize=(9, 6))
sc = ax.scatter(
    segs["rep_cpa"], segs["inc_cpa"],
    s=segs["spend"] / 2_500,
    c=segs["lift"],
    cmap="RdYlGn", vmin=0.0, vmax=0.70,
    alpha=0.85, edgecolors="white", linewidth=0.8, zorder=3,
)
ax.plot([40, 200], [40, 200], "k--", linewidth=0.7, alpha=0.3, zorder=2)
ax.text(148, 136, "Reported = Incremental", fontsize=7.5, alpha=0.4, rotation=54)

for _, r in segs.iterrows():
    ax.annotate(
        r["label"], (r["rep_cpa"], r["inc_cpa"]),
        xytext=(7, 4), textcoords="offset points",
        fontsize=8, color="#333333",
    )

plt.colorbar(sc, ax=ax, label="Incremental lift rate")
ax.set_xlabel("Reported CPA (€)", fontsize=11)
ax.set_ylabel("True incremental CPA (€)", fontsize=11)
ax.set_title(
    "Audiences that look cheapest are often the most expensive in reality\n"
    "Bubble size = spend  ·  Colour = incremental lift rate",
    fontsize=10, fontweight="bold",
)
ax.set_xlim(40, 185)
ax.set_ylim(80, 900)
plt.tight_layout()
plt.savefig("images/chart_2_cpa.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved chart_2_cpa.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 3 — Incremental CVR by frequency band
#
# Ads are most effective between 6 and 9 impressions per user per month.
# After 9, returns fall. After 20, the data shows a small negative effect —
# ad fatigue suppressing organic conversion.
# ─────────────────────────────────────────────────────────────────────────────
freq_df = pd.DataFrame({
    "band":   ["1–2", "3–5", "6–9", "10–14", "15–20", "21+"],
    "all":    [0.038, 0.046, 0.049,  0.047,   0.042,  0.036],
    "retarg": [0.041, 0.048, 0.046,  0.040,   0.033,  0.028],
})
x = range(len(freq_df))

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(x, freq_df["all"],    color=BLUE,  linewidth=2.2, marker="o", markersize=6,
        label="All audiences")
ax.plot(x, freq_df["retarg"], color=RED,   linewidth=2.2, marker="o", markersize=6,
        linestyle="--", label="Retargeting only")

# Mark the waste boundary — returns start falling after "6–9"
ax.axvline(x=2.5, color="gray", linewidth=1.0, linestyle=":", alpha=0.6)
ax.text(2.55, 0.0485, "Waste starts here", fontsize=8.5, color="gray", va="top")

ax.set_xticks(x)
ax.set_xticklabels(freq_df["band"])
ax.set_xlabel("Monthly impressions per user", fontsize=11)
ax.set_ylabel("Incremental conversion rate", fontsize=11)
ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=1))
ax.set_title(
    "Diminishing returns set in after 9 impressions — retargeting peaks earlier",
    fontsize=11, fontweight="bold",
)
ax.legend(frameon=False, fontsize=9)
plt.tight_layout()
plt.savefig("images/chart_3_frequency.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved chart_3_frequency.png")


# ─────────────────────────────────────────────────────────────────────────────
# CHART 4 — Waterfall: incremental conversion bridge
#
# Starts at the current 26,400 incremental conversions.
# Cutting retargeting loses some conversions (the real ones, not the claimed ones).
# Scaling prospecting adds significantly more.
# Net result: +8,400 conversions per month at zero additional spend.
# ─────────────────────────────────────────────────────────────────────────────
START   = 26_400
LOSS    =  4_200
GAIN    = 12_600
END     = START - LOSS + GAIN  # 34,800

fig, ax = plt.subplots(figsize=(8, 5))

# Bar 1 — current baseline
ax.bar(0, START, color=BLUE, width=0.5, zorder=3)
ax.text(0, START + 400, f"{START:,}", ha="center", fontsize=9, fontweight="bold")

# Bar 2 — retargeting cuts (shows the drop from START down by LOSS)
ax.bar(1, LOSS, bottom=START - LOSS, color=RED, width=0.5, zorder=3)
ax.text(1, START - LOSS / 2, f"−{LOSS:,}", ha="center", fontsize=9,
        color="white", fontweight="bold", va="center")

# Bar 3 — prospecting scale (builds up from START - LOSS)
ax.bar(2, GAIN, bottom=START - LOSS, color=GREEN, width=0.5, zorder=3)
ax.text(2, START - LOSS + GAIN + 400, f"+{GAIN:,}", ha="center", fontsize=9,
        color="#2E7D32", fontweight="bold")

# Bar 4 — optimised total
ax.bar(3, END, color=BLUE, width=0.5, zorder=3)
ax.text(3, END + 400, f"{END:,}", ha="center", fontsize=9, fontweight="bold")

# Connector line showing the running total
ax.plot([0.25, 0.75], [START, START],         color="gray", linewidth=0.7, linestyle=":", alpha=0.5)
ax.plot([1.25, 1.75], [START - LOSS, START - LOSS], color="gray", linewidth=0.7, linestyle=":", alpha=0.5)
ax.plot([2.25, 2.75], [END, END],             color="gray", linewidth=0.7, linestyle=":", alpha=0.5)

ax.set_xticks([0, 1, 2, 3])
ax.set_xticklabels(["Current\n(baseline)", "Retargeting\ncuts", "Prospecting\nscale", "Optimised"], fontsize=10)
ax.set_ylabel("Incremental conversions / month", fontsize=11)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
ax.set_ylim(0, 42_000)
ax.set_title(
    "Reallocation adds +8,400 incremental conversions at zero additional budget",
    fontsize=11, fontweight="bold",
)
ax.legend(handles=[
    Patch(color=RED,   label="Lost from retargeting cuts"),
    Patch(color=GREEN, label="Gained from prospecting scale"),
], frameon=False, fontsize=9, loc="upper left")

plt.tight_layout()
plt.savefig("images/chart_4_waterfall.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved chart_4_waterfall.png")

print("\nAll charts saved to images/")
