# Incrementality-Driven Audience Targeting for Paid Media

> **€6.5M/month - France - UK - Germany  TikTok, Meta, YouTube · Q3 2025**

---

**Dashboards showed 3.0× ROAS. Real performance was 1.25×.**

Reported CPA: €106. True CPA: €246. The €140 gap is the cost of taking credit for purchases that would have happened anyway.

Propensity Score Matching was applied to 340K users to separate which audiences the ads actually drove and which ones would have converted anyway.

---

**Repo contents:**
- `README.md`  case study and business recommendations
- `sql/`  BigQuery queries for exploration, matching prep, and lift analysis
- `python/`  PSM pipeline and budget simulation
- `images/`  final charts

---

## Executive Summary

**The problem.** €2.9M/month is currently allocated to retargeting. Hot retargeting shows €55 CPA in the dashboard. The real cost, once you strip out users who were buying anyway, is €500.

**What that means.** 57% of attributed conversions aren't incremental. They're organic purchases that happened to touch an ad. That revenue would have happened regardless.

**What to change.** Move €1.3M from retargeting into TikTok and Meta prospecting. Cap retargeting at 9 impressions per user per month. That's it.

**What you'd get.** +8,400 incremental conversions per month. True CPA drops from €246 to €187. +€30.2M in actual new revenue per year. No budget increase.

---

## The Problem

Platform attribution gives credit to any ad the user saw in the 7 days before purchasing. That's not causation, that's just proximity.

Retargeting targets people who already abandoned a cart, already visited the site multiple times, already searched the brand. These users were going to buy. An ad was shown, they purchased, and the platform took credit.

This is selection bias at scale. The audiences with the highest CVR have the highest purchase intent regardless of any ad exposure. Reported metrics measure intent, not impact.

---

## Data

Three BigQuery tables, 340K users, Q3 2025.

| Table | Key fields |
|-------|-----------|
| `media.impressions` | `user_id`, `channel`, `audience_type`, `impression_ts`, `spend_eur`, `frequency` |
| `events.conversions` | `user_id`, `conversion_ts`, `revenue_eur`, `is_first_purchase` |
| `crm.user_features` | `n_prior_purchases`, `n_organic_sessions_30d`, `days_since_last_visit`, `loyalty_tier`, `age_group` |

**Treatment:** saw at least one paid impression in a 30-day window.  
**Control:** visited the site but saw zero paid ads in the same window.  
**Outcome:** purchased within 7 days.

---

## Measurement Approach

The core problem: people who saw ads are not a random sample. Platforms deliberately serve impressions to users most likely to buy. So if you compare "people who saw ads" vs. "people who didn't", you're not measuring the ad effect, you're measuring the fact that platforms targeted high-intent users.

Propensity Score Matching addresses this directly. For each exposed user, the model finds an unexposed user who looked identical before the campaign, same purchase history, same visit frequency, same loyalty status. Comparing what each pair did isolates the causal ad effect.

**Variables used for matching (all measured before any ad exposure):**  
`n_prior_purchases` · `days_since_last_visit` · `n_organic_sessions_30d` · `loyalty_tier` · `email_subscriber` · `age_group` · `device_type` · `country`

**Setup:** 1:1 nearest-neighbour matching, caliper = 0.01, matched within country × channel. After matching, the two groups are statistically indistinguishable on all covariates (SMD < 0.1 across the board).

**→ Chart 1  Propensity score distribution, before and after matching.**  
Two histograms side by side. Before matching: the treated group skews heavily toward high propensity scores  they were targeted because they were high-intent. After matching: the distributions overlap almost perfectly. That overlap is what makes the comparison valid.

![Propensity score distribution before and after matching](images/chart_1_propensity.png)

---

## What We Found

### The rankings flip entirely

| Audience | Spend | Reported CPA | Lift Rate | True Inc. CPA | Call |
|----------|-------|-------------|-----------|---------------|------|
| TikTok Broad 18–24 | €683K | €85 | 62% | **€137** | Scale |
| Meta LAL 1% | €813K | €92 | 61% | **€151** | Scale |
| Meta LAL 3–5% | €488K | €105 | 59% | **€178** | Scale |
| TikTok Broad 25–34 | €455K | €98 | 57% | **€172** | Scale |
| TikTok Retargeting | €455K | €72 | 21% | €343 | Cut |
| Meta Retargeting Warm | €878K | €90 | 19% | €474 | Cut |
| Meta Retargeting Hot | €683K | €55 | 11% | €500 | Cut |
| YouTube Retargeting | €650K | €75 | 9% | **€833** | Cut |

The audiences that look cheapest in the dashboard are the most expensive once measured correctly. The ones that look expensive are doing real work.

**→ Chart 2  Reported CPA vs Incremental CPA, bubble chart.**  
X-axis: reported CPA. Y-axis: true incremental CPA. Bubble size: spend. Colour: lift rate  red for low, green for high. Retargeting sits bottom-left (cheap reported CPA) and top-right (expensive true CPA). Prospecting is the opposite. Show this chart first in any leadership meeting.

![Reported CPA vs incremental CPA by audience](images/chart_2_cpa.png)

---

## Frequency: burning money past 9 impressions

| Frequency band | Incremental CVR | Change vs. baseline |
|----------------|----------------|---------------------|
| 1–2 | 3.8% |  |
| 3–5 | 4.6% | +21% |
| **6–9** | **4.9%** | **+29%  peak** |
| 10–14 | 4.7% | +24% |
| 15–20 | 4.2% | +11% |
| 21+ | 3.6% | −5% |

Ads start losing effectiveness after 9 impressions. After 20, they actively hurt  users convert below their organic baseline. Some TikTok line items ran with no frequency cap. Meta retargeting hit 60+ impressions per month for certain users. That spend is not neutral  it's counterproductive.

**→ Chart 3  Incremental CVR by frequency band.**  
Line chart with two series: all audiences combined, and retargeting only. Retargeting peaks earlier and drops off harder. Add a dashed vertical line at frequency 9 labelled "waste starts here."

![Incremental CVR by frequency band](images/chart_3_frequency.png)
