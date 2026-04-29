-- =============================================================================
-- 03_incrementality_metrics.sql
-- Post-matching incrementality metrics by segment
-- Input: `prod.analysis.matched_pairs` produced by causal_model.py
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Incremental lift by channel × audience type
--    matched_pairs schema: treated_user_id, control_user_id, channel,
--                          audience_type, country, treated_converted,
--                          control_converted
-- ─────────────────────────────────────────────────────────────────────────────
WITH pair_outcomes AS (
    SELECT
        mp.channel,
        mp.audience_type,
        mp.country,
        mp.treated_converted,
        mp.control_converted,
        (mp.treated_converted - mp.control_converted)  AS pair_incremental_effect,
        s.total_spend_eur
    FROM `prod.analysis.matched_pairs` mp
    LEFT JOIN `prod.analysis.treated_users` s
        ON mp.treated_user_id = s.user_id
           AND mp.channel = s.channel
           AND mp.audience_type = s.audience_type
),

segment_lift AS (
    SELECT
        channel,
        audience_type,
        country,
        COUNT(*)                                        AS matched_pairs,
        AVG(treated_converted)                          AS treated_cvr,
        AVG(control_converted)                          AS control_cvr,
        AVG(pair_incremental_effect)                    AS incremental_cvr,
        -- Lift rate = what fraction of treated conversions are truly incremental
        SAFE_DIVIDE(
            AVG(pair_incremental_effect),
            AVG(treated_converted)
        )                                               AS lift_rate,
        SUM(total_spend_eur)                            AS segment_spend_eur
    FROM pair_outcomes
    GROUP BY 1, 2, 3
)

SELECT
    channel,
    audience_type,
    country,
    matched_pairs,
    ROUND(treated_cvr,  4)                              AS treated_cvr,
    ROUND(control_cvr,  4)                              AS control_cvr,
    ROUND(incremental_cvr, 4)                           AS incremental_cvr,
    ROUND(lift_rate, 3)                                 AS lift_rate,
    ROUND(segment_spend_eur, 0)                         AS spend_eur,
    -- Incremental conversions estimated for full population (not just matched sample)
    ROUND(incremental_cvr * matched_pairs, 0)           AS est_incremental_conversions,
    -- True incremental CPA
    SAFE_DIVIDE(
        segment_spend_eur,
        incremental_cvr * matched_pairs
    )                                                   AS incremental_cpa
FROM segment_lift
ORDER BY lift_rate DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Aggregate portfolio view — reported vs incremental
-- ─────────────────────────────────────────────────────────────────────────────
WITH reported AS (
    SELECT
        SUM(s.spend_eur)                AS total_spend,
        COUNT(DISTINCT c.conversion_id) AS reported_conversions,
        SUM(c.revenue_eur)              AS reported_revenue
    FROM `prod.media.impressions` s
    LEFT JOIN `prod.events.conversions` c
        ON s.user_id = c.user_id
        AND c.conversion_ts BETWEEN s.impression_ts
                                AND TIMESTAMP_ADD(s.impression_ts, INTERVAL 7 DAY)
    WHERE s.impression_ts BETWEEN '2025-07-01' AND '2025-09-30'
),

incremental AS (
    SELECT
        SUM(s.total_spend_eur)                          AS total_spend,
        SUM(
            mp.treated_converted - mp.control_converted
        )                                               AS incremental_conversions
    FROM `prod.analysis.matched_pairs` mp
    LEFT JOIN `prod.analysis.treated_users` s
        ON mp.treated_user_id = s.user_id
)

SELECT
    'Reported'      AS measurement_type,
    r.total_spend,
    r.reported_conversions                              AS conversions,
    r.reported_revenue                                  AS revenue,
    SAFE_DIVIDE(r.total_spend, r.reported_conversions)  AS cpa,
    SAFE_DIVIDE(r.reported_revenue, r.total_spend)      AS roas
FROM reported r

UNION ALL

SELECT
    'Incremental'   AS measurement_type,
    i.total_spend,
    i.incremental_conversions                           AS conversions,
    i.incremental_conversions * 300.0                   AS revenue,  -- AOV = €300
    SAFE_DIVIDE(i.total_spend, i.incremental_conversions) AS cpa,
    SAFE_DIVIDE(i.incremental_conversions * 300.0, i.total_spend) AS roas
FROM incremental i;


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Frequency vs incremental CVR — using matched pairs
--    Isolates the causal frequency effect by comparing treated users
--    at different frequency levels to their matched controls
-- ─────────────────────────────────────────────────────────────────────────────
WITH pair_frequency AS (
    SELECT
        mp.treated_user_id,
        tu.total_impressions,
        CASE
            WHEN tu.total_impressions BETWEEN 1  AND 2  THEN '01-02'
            WHEN tu.total_impressions BETWEEN 3  AND 5  THEN '03-05'
            WHEN tu.total_impressions BETWEEN 6  AND 9  THEN '06-09'
            WHEN tu.total_impressions BETWEEN 10 AND 14 THEN '10-14'
            WHEN tu.total_impressions BETWEEN 15 AND 20 THEN '15-20'
            ELSE '21+'
        END                                             AS freq_band,
        mp.treated_converted,
        mp.control_converted,
        (mp.treated_converted - mp.control_converted)   AS incremental_effect
    FROM `prod.analysis.matched_pairs` mp
    INNER JOIN `prod.analysis.treated_users` tu
        ON mp.treated_user_id = tu.user_id
)

SELECT
    freq_band,
    COUNT(*)                            AS pairs,
    AVG(treated_converted)              AS treated_cvr,
    AVG(control_converted)              AS control_cvr,
    AVG(incremental_effect)             AS incremental_cvr,
    SAFE_DIVIDE(
        AVG(incremental_effect),
        AVG(treated_converted)
    )                                   AS lift_rate
FROM pair_frequency
GROUP BY 1
ORDER BY freq_band;
