"""
Propensity Score Matching for Paid Media Incrementality Analysis
Project: Incrementality-Driven Audience Targeting — EUI Markets

Inputs:  psm_dataset (from 02_psm_prep.sql, loaded as DataFrame)
Outputs: matched_pairs DataFrame, balance report, lift metrics by segment
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from scipy import stats


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

CALIPER = 0.01          # max allowed difference in propensity score (logit scale)
RANDOM_STATE = 42
CATEGORICAL_FEATURES = [
    "age_group", "device_type", "loyalty_tier", "category_affinity", "country"
]
NUMERIC_FEATURES = [
    "n_prior_purchases", "n_organic_sessions_30d", "days_since_last_visit"
]
BINARY_FEATURES = ["email_subscriber"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Data loading (replace with BigQuery client in production)
# ─────────────────────────────────────────────────────────────────────────────

def load_data(path: str = "data/psm_dataset.parquet") -> pd.DataFrame:
    """Load PSM dataset. In production: google.cloud.bigquery.Client."""
    return pd.read_parquet(path)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Feature engineering
# ─────────────────────────────────────────────────────────────────────────────

def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    encoded = pd.get_dummies(df[CATEGORICAL_FEATURES], drop_first=True)
    numeric = df[NUMERIC_FEATURES].fillna(0)
    binary  = df[BINARY_FEATURES].astype(int)
    return pd.concat([numeric, binary, encoded], axis=1)


def standardise(X_train: pd.DataFrame, X_all: pd.DataFrame):
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_all_sc   = scaler.transform(X_all)
    return X_train_sc, X_all_sc, scaler


# ─────────────────────────────────────────────────────────────────────────────
# 3. Propensity score estimation
# ─────────────────────────────────────────────────────────────────────────────

def estimate_propensity(df: pd.DataFrame, X: np.ndarray) -> np.ndarray:
    model = LogisticRegression(
        max_iter=500,
        C=1.0,
        solver="lbfgs",
        random_state=RANDOM_STATE
    )
    model.fit(X, df["treatment"])
    ps = model.predict_proba(X)[:, 1]
    auc = roc_auc_score(df["treatment"], ps)
    print(f"Propensity model AUC: {auc:.3f}")
    return ps


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


# ─────────────────────────────────────────────────────────────────────────────
# 4. 1:1 Nearest-neighbour matching with caliper
--   Matching is performed within country × channel to avoid cross-market noise
# ─────────────────────────────────────────────────────────────────────────────

def match_within_segment(
    treated: pd.DataFrame,
    control: pd.DataFrame,
    caliper: float = CALIPER
) -> pd.DataFrame:
    """
    Nearest-neighbour 1:1 matching without replacement.
    Returns DataFrame with treated_idx, control_idx, and distance.
    """
    treated_logit = logit(treated["propensity_score"].values)
    control_logit = logit(control["propensity_score"].values)

    used_control = set()
    pairs = []

    for i, t_val in enumerate(treated_logit):
        distances = np.abs(control_logit - t_val)
        # Mask already-matched controls
        mask = np.array([j not in used_control for j in range(len(control_logit))])
        distances[~mask] = np.inf

        best_j = distances.argmin()
        if distances[best_j] <= caliper:
            pairs.append({
                "treated_idx":    treated.index[i],
                "control_idx":    control.index[best_j],
                "ps_distance":    distances[best_j],
                "treated_ps":     treated["propensity_score"].iloc[i],
                "control_ps":     control["propensity_score"].iloc[best_j],
            })
            used_control.add(best_j)

    return pd.DataFrame(pairs)


def run_matching(df: pd.DataFrame) -> pd.DataFrame:
    all_pairs = []

    for (country, channel, aud_type), group in df.groupby(
        ["country", "channel", "audience_type"]
    ):
        treated = group[group["treatment"] == 1].copy()
        control = group[group["treatment"] == 0].copy()

        if len(treated) < 10 or len(control) < 10:
            continue

        pairs = match_within_segment(treated, control)
        pairs["country"]       = country
        pairs["channel"]       = channel
        pairs["audience_type"] = aud_type
        all_pairs.append(pairs)

        print(
            f"  {country} | {channel} | {aud_type}: "
            f"{len(treated)} treated → {len(pairs)} matched pairs "
            f"({100 * len(pairs) / len(treated):.0f}% matched)"
        )

    return pd.concat(all_pairs, ignore_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Balance diagnostics — Standardised Mean Differences
# ─────────────────────────────────────────────────────────────────────────────

def standardised_mean_diff(series_a: pd.Series, series_b: pd.Series) -> float:
    pooled_std = np.sqrt((series_a.var() + series_b.var()) / 2)
    if pooled_std == 0:
        return 0.0
    return (series_a.mean() - series_b.mean()) / pooled_std


def balance_report(df: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    treated_all = df[df["treatment"] == 1]
    control_all = df[df["treatment"] == 0]
    treated_matched = df.loc[pairs["treated_idx"]]
    control_matched = df.loc[pairs["control_idx"]]

    rows = []
    for col in NUMERIC_FEATURES + BINARY_FEATURES:
        rows.append({
            "feature":            col,
            "smd_before":         standardised_mean_diff(
                                      treated_all[col], control_all[col]),
            "smd_after":          standardised_mean_diff(
                                      treated_matched[col], control_matched[col]),
        })

    report = pd.DataFrame(rows)
    report["balance_achieved"] = report["smd_after"].abs() < 0.1
    print("\nBalance report (SMD < 0.1 = acceptable):")
    print(report.to_string(index=False))
    return report


# ─────────────────────────────────────────────────────────────────────────────
# 6. Incrementality metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_lift(df: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    pairs = pairs.copy()
    pairs["treated_converted"] = df.loc[pairs["treated_idx"], "converted"].values
    pairs["control_converted"]  = df.loc[pairs["control_idx"],  "converted"].values
    pairs["incremental"]        = pairs["treated_converted"] - pairs["control_converted"]

    results = []
    for (country, channel, aud_type), grp in pairs.groupby(
        ["country", "channel", "audience_type"]
    ):
        n              = len(grp)
        treated_cvr    = grp["treated_converted"].mean()
        control_cvr    = grp["control_converted"].mean()
        inc_cvr        = grp["incremental"].mean()
        lift_rate      = inc_cvr / treated_cvr if treated_cvr > 0 else np.nan

        # Two-proportion z-test for statistical significance
        successes = [
            grp["treated_converted"].sum(),
            grp["control_converted"].sum()
        ]
        nobs = [n, n]
        _, p_value = stats.proportions_ztest(successes, nobs)

        results.append({
            "country":               country,
            "channel":               channel,
            "audience_type":         aud_type,
            "matched_pairs":         n,
            "treated_cvr":           round(treated_cvr,  4),
            "control_cvr":           round(control_cvr,  4),
            "incremental_cvr":       round(inc_cvr,      4),
            "lift_rate":             round(lift_rate,     3),
            "p_value":               round(p_value,       4),
            "significant_at_05":     p_value < 0.05,
        })

    return pd.DataFrame(results).sort_values("lift_rate", ascending=False)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Visualisations
# ─────────────────────────────────────────────────────────────────────────────

def plot_propensity_balance(
    df: pd.DataFrame,
    pairs: pd.DataFrame,
    save_path: str = "figures/propensity_balance.png"
) -> None:
    treated_all     = df[df["treatment"] == 1]["propensity_score"]
    control_all     = df[df["treatment"] == 0]["propensity_score"]
    treated_matched = df.loc[pairs["treated_idx"], "propensity_score"]
    control_matched = df.loc[pairs["control_idx"],  "propensity_score"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    for ax, (t, c, title) in zip(axes, [
        (treated_all,     control_all,     "Before Matching"),
        (treated_matched, control_matched, "After Matching"),
    ]):
        ax.hist(t, bins=40, alpha=0.6, label="Treated",  color="#E63946", density=True)
        ax.hist(c, bins=40, alpha=0.6, label="Control",  color="#457B9D", density=True)
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_xlabel("Propensity Score")
        ax.set_ylabel("Density")
        ax.legend()

    fig.suptitle(
        "Propensity Score Distribution — Common Support Check",
        fontsize=14, y=1.02
    )
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {save_path}")


def plot_lift_heatmap(
    lift_df: pd.DataFrame,
    save_path: str = "figures/lift_heatmap.png"
) -> None:
    pivot = lift_df.pivot_table(
        index="audience_type",
        columns="country",
        values="lift_rate",
        aggfunc="mean"
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".0%",
        cmap="RdYlGn",
        vmin=0,
        vmax=0.75,
        linewidths=0.5,
        ax=ax,
        cbar_kws={"label": "Incremental Lift Rate"}
    )
    ax.set_title(
        "Incremental Lift Rate by Audience Type × Country",
        fontsize=13, fontweight="bold"
    )
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {save_path}")


def plot_cpa_comparison(
    lift_df: pd.DataFrame,
    spend_by_segment: pd.DataFrame,
    aov: float = 300.0,
    save_path: str = "figures/cpa_comparison.png"
) -> None:
    merged = lift_df.merge(spend_by_segment, on=["country", "channel", "audience_type"])
    merged["incremental_conversions"] = merged["incremental_cvr"] * merged["matched_pairs"]
    merged["incremental_cpa"] = merged["total_spend_eur"] / merged["incremental_conversions"]
    merged["reported_cpa"]    = merged["total_spend_eur"] / (
        merged["treated_cvr"] * merged["matched_pairs"]
    )
    merged["segment_label"]   = (
        merged["channel"] + " · " + merged["audience_type"].str.replace("_", " ")
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    scatter = ax.scatter(
        merged["reported_cpa"],
        merged["incremental_cpa"],
        s=merged["total_spend_eur"] / 5000,
        c=merged["lift_rate"],
        cmap="RdYlGn",
        vmin=0,
        vmax=0.75,
        alpha=0.85,
        edgecolors="white",
        linewidth=0.8
    )
    max_val = max(merged["incremental_cpa"].max(), merged["reported_cpa"].max()) * 1.05
    ax.plot([0, max_val], [0, max_val], "k--", linewidth=0.8, alpha=0.4, label="Reported = Incremental")
    plt.colorbar(scatter, ax=ax, label="Incremental Lift Rate")
    ax.set_xlabel("Reported CPA (€)", fontsize=11)
    ax.set_ylabel("True Incremental CPA (€)", fontsize=11)
    ax.set_title(
        "Reported vs Incremental CPA by Audience Segment\n"
        "(Bubble size = spend | Colour = lift rate)",
        fontsize=12, fontweight="bold"
    )
    ax.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {save_path}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Budget reallocation simulation
# ─────────────────────────────────────────────────────────────────────────────

def simulate_reallocation(
    lift_df: pd.DataFrame,
    spend_by_segment: pd.DataFrame,
    reallocation_map: dict,  # {audience_type: new_spend_eur}
    aov: float = 300.0
) -> pd.DataFrame:
    """
    Projects incremental conversions and CPA under a new spend allocation.
    Assumes lift rate is constant within a moderate reallocation range (±40%).
    """
    merged = lift_df.merge(spend_by_segment, on=["country", "channel", "audience_type"])
    merged["current_inc_conv"] = merged["incremental_cvr"] * merged["matched_pairs"]
    merged["current_inc_cpa"]  = merged["total_spend_eur"] / merged["current_inc_conv"]

    rows = []
    for _, row in merged.iterrows():
        new_spend = reallocation_map.get(row["audience_type"], row["total_spend_eur"])
        scale_factor  = new_spend / row["total_spend_eur"] if row["total_spend_eur"] > 0 else 1
        new_inc_conv  = row["current_inc_conv"] * min(scale_factor, 1.8)  # diminishing returns cap
        rows.append({
            "audience_type":        row["audience_type"],
            "channel":              row["channel"],
            "country":              row["country"],
            "current_spend":        row["total_spend_eur"],
            "optimised_spend":      new_spend,
            "current_inc_conv":     row["current_inc_conv"],
            "optimised_inc_conv":   new_inc_conv,
            "current_inc_cpa":      row["current_inc_cpa"],
            "optimised_inc_cpa":    new_spend / new_inc_conv if new_inc_conv > 0 else np.nan,
        })

    sim = pd.DataFrame(rows)
    summary = {
        "total_budget":                sim["current_spend"].sum(),
        "current_incremental_conv":    sim["current_inc_conv"].sum(),
        "optimised_incremental_conv":  sim["optimised_inc_conv"].sum(),
        "conv_uplift_pct":             (
            sim["optimised_inc_conv"].sum() / sim["current_inc_conv"].sum() - 1
        ) * 100,
        "current_portfolio_inc_cpa":   (
            sim["current_spend"].sum() / sim["current_inc_conv"].sum()
        ),
        "optimised_portfolio_inc_cpa": (
            sim["optimised_spend"].sum() / sim["optimised_inc_conv"].sum()
        ),
        "incremental_revenue_uplift":  (
            (sim["optimised_inc_conv"].sum() - sim["current_inc_conv"].sum()) * aov
        ),
    }
    return sim, summary


# ─────────────────────────────────────────────────────────────────────────────
# 9. Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=== Incrementality Analysis — EUI Markets ===\n")

    df = load_data()
    print(f"Dataset: {len(df):,} users | {df['treatment'].mean():.1%} treated\n")

    X_raw = build_feature_matrix(df)
    X_sc, _, _ = standardise(X_raw, X_raw)

    df["propensity_score"] = estimate_propensity(df, X_sc)
    print()

    print("Running matching by segment...")
    pairs = run_matching(df)
    print(f"\nTotal matched pairs: {len(pairs):,}\n")

    balance = balance_report(df, pairs)
    if not balance["balance_achieved"].all():
        print("WARNING: Some features did not reach balance threshold (SMD < 0.1)")

    lift_df = compute_lift(df, pairs)
    print("\n--- Incremental Lift Results ---")
    print(lift_df.to_string(index=False))

    plot_propensity_balance(df, pairs)
    plot_lift_heatmap(lift_df)

    reallocation_map = {
        "prospecting_lal":    2_437_500,
        "prospecting_broad":  2_437_500,
        "retargeting_warm":     812_500,
        "retargeting_hot":      812_500,
    }
    spend_by_segment = (
        df[df["treatment"] == 1]
        .groupby(["country", "channel", "audience_type"])["total_spend_eur"]
        .sum()
        .reset_index()
    )
    sim, summary = simulate_reallocation(lift_df, spend_by_segment, reallocation_map)

    print("\n--- Reallocation Simulation ---")
    for k, v in summary.items():
        if "conv" in k or "pct" in k:
            print(f"  {k}: {v:,.0f}{'%' if 'pct' in k else ''}")
        else:
            print(f"  {k}: €{v:,.0f}")


if __name__ == "__main__":
    main()
