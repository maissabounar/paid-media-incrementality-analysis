# Incrementality-Driven Audience Targeting for Paid Media

> €6.5M/month · France · UK · Germany · TikTok, Meta, YouTube · Q3 2025

![ROAS](https://img.shields.io/badge/ROAS-1.25x-red)
![Budget](https://img.shields.io/badge/Budget-€6.5M-blue)
![Markets](https://img.shields.io/badge/Markets-FR_UK_DE-green)

---

Dashboards showed 3.0x ROAS.

Incrementality showed 1.25x.

Reported CPA was €106. True incremental CPA was €246.

That €140 gap is the cost of taking credit for conversions that would have happened anyway.

This project uses Propensity Score Matching on 340000 users to separate attributed conversions from incremental conversions.

---

## Executive Summary

| Metric | Reported | Incremental |
|---|---:|---:|
| Monthly conversions | 61425 | 26400 |
| CPA | €106 | €246 |
| ROAS | 3.0x | 1.25x |
| Non-incremental attributed conversions |  | 57% |

The biggest issue was retargeting.

Hot retargeting looked like the best audience in the dashboard with €55 CPA. After incrementality adjustment, it became one of the worst with €500 incremental CPA.

The recommendation: move €1.3M from retargeting to TikTok and Meta prospecting, cap retargeting frequency at 9 impressions per user per month, and replace reported CPA with incremental CPA as the primary media KPI.

Expected impact:

- +8400 incremental conversions per month
- True CPA down from €246 to €187
- +€30.2M annual incremental revenue
- No budget increase

---

## Business Problem

Platform attribution rewards proximity, not causality.

If a user sees an ad and purchases within 7 days, the platform takes credit.

That works poorly for retargeting.

Retargeting reaches users who already visited the site, abandoned a cart, searched the brand, or purchased before. Many of them were going to convert anyway.

The dashboard measured who was most likely to buy.

This analysis measured what the ads actually changed.

---

## Data

Three BigQuery tables, 340000 users, Q3 2025.

| Table | Key fields |
|---|---|
| `media.impressions` | `user_id`, `channel`, `audience_type`, `impression_ts`, `spend_eur`, `frequency` |
| `events.conversions` | `user_id`, `conversion_ts`, `revenue_eur`, `is_first_purchase` |
| `crm.user_features` | `n_prior_purchases`, `n_organic_sessions_30d`, `days_since_last_visit`, `loyalty_tier`, `age_group` |

| Element | Definition |
|---|---|
| Treatment | User saw at least one paid impression in a 30-day window |
| Control | User visited the site but saw zero paid ads in the same window |
| Outcome | User purchased within 7 days |

---

## Measurement Approach

Users exposed to ads were not random.

Platforms targeted users with higher purchase intent. A direct comparison between exposed and unexposed users would overstate media impact.

Propensity Score Matching fixes this by pairing each exposed user with a similar unexposed user based on pre-campaign behavior.

Matching variables:

- `n_prior_purchases`
- `days_since_last_visit`
- `n_organic_sessions_30d`
- `loyalty_tier`
- `email_subscriber`
- `age_group`
- `device_type`
- `country`

Setup:

| Method | Detail |
|---|---|
| Matching | 1:1 nearest neighbour |
| Caliper | 0.01 |
| Match level | Country × channel |
| Balance check | SMD < 0.1 across covariates |

After matching, the treated and control groups were comparable. The remaining conversion gap is the estimated incremental effect.

![Propensity score distribution before and after matching](images/chart_1_propensity.png)

---

## Findings

### 1. Audience rankings changed completely

| Audience | Spend | Reported CPA | Lift Rate | Incremental CPA | Decision |
|---|---:|---:|---:|---:|---|
| TikTok Broad 18–24 | €683K | €85 | 62% | €137 | Scale |
| Meta LAL 1% | €813K | €92 | 61% | €151 | Scale |
| Meta LAL 3–5% | €488K | €105 | 59% | €178 | Scale |
| TikTok Broad 25–34 | €455K | €98 | 57% | €172 | Scale |
| TikTok Retargeting | €455K | €72 | 21% | €343 | Cut |
| Meta Retargeting Warm | €878K | €90 | 19% | €474 | Cut |
| Meta Retargeting Hot | €683K | €55 | 11% | €500 | Cut |
| YouTube Retargeting | €650K | €75 | 9% | €833 | Cut |

The cheapest audiences in the dashboard became the most expensive after incrementality adjustment.

Retargeting looked efficient because it targeted high-intent users. Prospecting looked weaker because it reached colder users. Incrementality reversed that read.

![Reported CPA vs incremental CPA by audience](images/chart_2_cpa.png)

---

### 2. Retargeting took too much credit

| Metric | Reported | Incremental |
|---|---:|---:|
| Monthly conversions | 61425 | 26400 |
| CPA | €106 | €246 |
| ROAS | 3.0x | 1.25x |

61425 conversions were attributed to paid media.

Only 26400 were incremental.

The remaining 35025 conversions were likely organic demand captured by the attribution window.

---

### 3. Frequency waste started after 9 impressions

| Frequency band | Incremental CVR | Change vs baseline |
|---|---:|---:|
| 1–2 | 3.8% | — |
| 3–5 | 4.6% | +21% |
| 6–9 | 4.9% | +29% |
| 10–14 | 4.7% | +24% |
| 15–20 | 4.2% | +11% |
| 21+ | 3.6% | -5% |

Incremental conversion rate peaked at 6–9 impressions.

After 20 impressions, users converted below their organic baseline.

Some TikTok line items had no frequency cap. Some Meta retargeting users reached 60+ impressions per month.

That spend was not neutral. It reduced efficiency.

![Incremental CVR by frequency band](images/chart_3_frequency.png)

---

### 4. Creative impact depended on audience intent

UGC creative outperformed branded studio content by 17 percentage points on incremental lift.

The reason was not production cost.

UGC reached users with lower baseline intent, where the ad had more room to change behavior. Branded studio content performed better among warm users, but those users were less incremental.

For prospecting, UGC should be the default.

---

### 5. Germany was underinvested in prospecting

Germany had the highest retargeting share at 42% of spend.

It also had the lowest brand awareness across the three markets.

That means the market with the largest opportunity for new demand was spending the most defensively.

Germany should receive more prospecting budget, not more retargeting pressure.

---

## Budget Reallocation

Move €1.3M from retargeting to prospecting.

Total spend stays flat.

| Metric | Current | Optimized | Change |
|---|---:|---:|---:|
| Prospecting spend | €3.575M | €4.875M | +€1.3M |
| Retargeting spend | €2.925M | €1.625M | -€1.3M |
| Incremental conversions/month | 26400 | 34800 | +32% |
| True CPA | €246 | €187 | -24% |
| Annual incremental revenue | — | +€30.2M | — |

![Budget reallocation waterfall](images/chart_4_waterfall.png)

> [!IMPORTANT]
> Reported CPA will likely get worse after this change.
>
> That is expected. Prospecting reaches users who were not already about to convert. If the team keeps optimizing on reported CPA, the budget will drift back to retargeting and the incrementality gain will disappear.

---

## Recommendations

| # | Action | Timing | Expected impact |
|---:|---|---|---|
| 1 | Pause YouTube retargeting and move budget to YouTube prospecting | Now | Replace 9% lift with 56% lift |
| 2 | Cap retargeting at 9 impressions per user per month | Now | Recover around €380K/month |
| 3 | Shift €1.3M from retargeting to TikTok and Meta LAL prospecting | 30 days | +8400 incremental conversions/month |
| 4 | Make UGC the default creative for prospecting | 30 days | +17pp lift rate |
| 5 | Replace reported CPA with incremental CPA as the primary KPI | 90 days | Fix the optimization loop |

---

## Operating Model

### Monthly refresh

Run the PSM pipeline every month in Airflow.

Inputs:

- Updated CRM features from the CDP
- Latest media exposure data
- Latest conversion data

Outputs:

- Incremental CPA by channel
- Lift rate by audience
- Frequency efficiency curve
- Budget reallocation view

The output writes back to BigQuery and feeds the media planning dashboard.

### Quarterly validation

Hold out 10% of users in France from paid media every quarter.

Compare:

- Geo or user holdout result
- PSM-based incremental lift estimate

If the gap is above 5 percentage points, retrain the model and review targeting logic.

### Governance

Incrementality metrics need to sit next to platform metrics.

If incremental CPA lives in a separate analysis deck, buyers will keep optimizing toward reported CPA.

---

## How to Reproduce

Run from the project root.

```bash
pip install -r requirements.txt
python python/generate_data.py
python python/generate_charts.py
```

> [!NOTE]
> A sample dataset is included. The full synthetic dataset can be regenerated via script.

`generate_data.py` creates a 20000-user synthetic dataset with the schema described above.

`generate_charts.py` runs propensity matching and renders all four charts.

---

## Repo Contents

```text
incrementality-driven-audience-targeting/
├── README.md
├── requirements.txt
├── data/
│   └── synthetic_data.csv
├── images/
│   ├── chart_1_propensity.png
│   ├── chart_2_cpa.png
│   ├── chart_3_frequency.png
│   └── chart_4_waterfall.png
├── sql/
│   ├── 01_baseline_intent.sql
│   ├── 02_matching_prep.sql
│   ├── 03_lift_analysis.sql
│   └── 04_budget_reallocation.sql
└── python/
    ├── generate_data.py
    ├── psm_pipeline.py
    └── generate_charts.py
```

---

## Code Overview

| File | Purpose |
|---|---|
| `python/generate_data.py` | Generates synthetic user, media, conversion, and CRM data |
| `python/psm_pipeline.py` | Estimates propensity scores, matches users, checks balance, and calculates incremental lift |
| `python/generate_charts.py` | Generates the charts used in the README |
| `sql/01_baseline_intent.sql` | Checks selection bias by audience before modeling |
| `sql/02_matching_prep.sql` | Builds the user-level modeling table |
| `sql/03_lift_analysis.sql` | Calculates incremental CVR, lift rate, and incremental CPA |
| `sql/04_budget_reallocation.sql` | Simulates budget shifts from retargeting to prospecting |

---

## Key SQL Check

Before any modeling, check whether retargeting users already had higher intent.

```sql
SELECT
    audience_type,
    AVG(f.n_prior_purchases)      AS avg_prior_purchases,
    AVG(f.n_organic_sessions_30d) AS avg_organic_sessions,
    AVG(p.converted)              AS reported_cvr
FROM `prod.analysis.psm_dataset` p
JOIN `prod.crm.user_features` f USING (user_id)
WHERE treatment = 1
GROUP BY 1
ORDER BY avg_prior_purchases DESC;
```

Expected result: hot retargeting ranks highest on prior purchases, organic sessions, and reported CVR.

That is the selection bias.

---

## Core Python Logic

```python
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

FEATURES = [
    "n_prior_purchases",
    "n_organic_sessions_30d",
    "days_since_last_visit",
    "email_subscriber",
    "age_group_enc",
    "device_type_enc",
    "loyalty_tier_enc",
]

def estimate_propensity(df: pd.DataFrame) -> pd.DataFrame:
    model = LogisticRegression(max_iter=500, C=1.0)
    model.fit(df[FEATURES], df["treatment"])

    propensity_score = model.predict_proba(df[FEATURES])[:, 1]
    df["ps"] = np.clip(propensity_score, 1e-6, 1 - 1e-6)
    df["logit_ps"] = np.log(df["ps"] / (1 - df["ps"]))

    return df

def match(df: pd.DataFrame, caliper: float = 0.01) -> pd.DataFrame:
    pairs = []

    for _, group in df.groupby(["country", "channel", "audience_type"]):
        treated = group[group["treatment"] == 1]
        control = group[group["treatment"] == 0]
        used_controls = set()

        for treated_idx, treated_row in treated.iterrows():
            distances = (control["logit_ps"] - treated_row["logit_ps"]).abs()
            distances[control.index.isin(used_controls)] = np.inf

            control_idx = distances.idxmin()

            if distances[control_idx] <= caliper:
                pairs.append({
                    "treated_idx": treated_idx,
                    "control_idx": control_idx,
                    "channel": treated_row["channel"],
                    "audience_type": treated_row["audience_type"],
                    "country": treated_row["country"],
                })
                used_controls.add(control_idx)

    return pd.DataFrame(pairs)
```

---

## Methods

- Incrementality measurement
- Propensity Score Matching
- Selection bias diagnosis
- Paid media performance analysis
- Audience strategy
- Frequency cap analysis
- Budget reallocation simulation
- BigQuery SQL
- Python modeling pipeline
- Executive business recommendations

The key point: the dashboard showed efficient media. Incrementality showed where the ads actually created demand.
