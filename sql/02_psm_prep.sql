-- =============================================================================
-- 02_psm_prep.sql
-- Feature engineering for propensity score model
-- Produces one row per user with treatment flag and pre-exposure covariates
-- Output table consumed by causal_model.py
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- Step 1: Define the exposed (treatment) population
--         Users who received ≥1 paid impression in the analysis window
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `prod.analysis.treated_users` AS
SELECT
    user_id,
    channel,
    audience_type,
    country,
    MIN(impression_ts)          AS first_impression_ts,
    MAX(impression_ts)          AS last_impression_ts,
    COUNT(impression_id)        AS total_impressions,
    SUM(spend_eur)              AS total_spend_eur
FROM `prod.media.impressions`
WHERE impression_ts BETWEEN '2025-07-01' AND '2025-09-30'
GROUP BY 1, 2, 3, 4;


-- ─────────────────────────────────────────────────────────────────────────────
-- Step 2: Define the control pool
--         Users present in site event logs but with zero paid impressions.
--         These are organically-active users who were eligible but not reached.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `prod.analysis.control_pool` AS
SELECT DISTINCT
    e.user_id,
    f.country
FROM `prod.events.site_sessions` e            -- all cookied/identified sessions
LEFT JOIN `prod.analysis.treated_users` t USING (user_id)
INNER JOIN `prod.crm.user_features` f USING (user_id)
WHERE t.user_id IS NULL                       -- exclude anyone exposed to paid media
  AND e.session_ts BETWEEN '2025-07-01' AND '2025-09-30';


-- ─────────────────────────────────────────────────────────────────────────────
-- Step 3: Build the modelling dataset — one row per user
--         All covariates are PRE-EXPOSURE to prevent data leakage
--         Outcome: converted within 30 days of exposure (or within window for controls)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `prod.analysis.psm_dataset` AS

WITH treatment_rows AS (
    SELECT
        t.user_id,
        t.channel,
        t.audience_type,
        t.country,
        1                               AS treatment,
        t.total_impressions,
        t.total_spend_eur,
        -- Covariates
        f.age_group,
        f.device_type,
        f.email_subscriber,
        f.n_prior_purchases,
        f.n_organic_sessions_30d,
        f.days_since_last_visit,
        f.loyalty_tier,
        f.category_affinity,
        -- Outcome: converted within 30-day attribution window
        CASE WHEN c.user_id IS NOT NULL THEN 1 ELSE 0 END AS converted
    FROM `prod.analysis.treated_users` t
    INNER JOIN `prod.crm.user_features` f USING (user_id)
    LEFT JOIN (
        SELECT DISTINCT user_id
        FROM `prod.events.conversions`
        WHERE conversion_ts BETWEEN '2025-07-01' AND '2025-09-30'
    ) c USING (user_id)
),

control_rows AS (
    SELECT
        cp.user_id,
        NULL                            AS channel,
        NULL                            AS audience_type,
        cp.country,
        0                               AS treatment,
        0                               AS total_impressions,
        0.0                             AS total_spend_eur,
        -- Covariates
        f.age_group,
        f.device_type,
        f.email_subscriber,
        f.n_prior_purchases,
        f.n_organic_sessions_30d,
        f.days_since_last_visit,
        f.loyalty_tier,
        f.category_affinity,
        -- Outcome
        CASE WHEN c.user_id IS NOT NULL THEN 1 ELSE 0 END AS converted
    FROM `prod.analysis.control_pool` cp
    INNER JOIN `prod.crm.user_features` f USING (user_id)
    LEFT JOIN (
        SELECT DISTINCT user_id
        FROM `prod.events.conversions`
        WHERE conversion_ts BETWEEN '2025-07-01' AND '2025-09-30'
    ) c USING (user_id)
)

SELECT * FROM treatment_rows
UNION ALL
SELECT * FROM control_rows;


-- ─────────────────────────────────────────────────────────────────────────────
-- Step 4: Sanity check — population sizes and balance before matching
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    treatment,
    COUNT(*)                            AS n_users,
    AVG(n_prior_purchases)              AS avg_prior_purchases,
    AVG(n_organic_sessions_30d)         AS avg_organic_sessions,
    AVG(days_since_last_visit)          AS avg_days_since_visit,
    COUNTIF(email_subscriber) / COUNT(*) AS pct_email_sub,
    AVG(converted)                      AS baseline_cvr
FROM `prod.analysis.psm_dataset`
GROUP BY 1
ORDER BY 1;
