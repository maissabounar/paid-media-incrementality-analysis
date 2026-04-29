-- =============================================================================
-- 01_data_exploration.sql
-- Baseline performance analysis — reported metrics before causal adjustment
-- Project: Incrementality-Driven Audience Targeting, EUI Markets
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Monthly spend and reported performance by channel × audience type
-- ─────────────────────────────────────────────────────────────────────────────
WITH impression_spend AS (
    SELECT
        channel,
        audience_type,
        country,
        DATE_TRUNC(impression_ts, MONTH)    AS month,
        COUNT(DISTINCT user_id)             AS reached_users,
        SUM(spend_eur)                      AS total_spend_eur,
        COUNT(impression_id)                AS total_impressions
    FROM `prod.media.impressions`
    WHERE impression_ts BETWEEN '2025-07-01' AND '2025-09-30'
    GROUP BY 1, 2, 3, 4
),

attributed_conversions AS (
    SELECT
        i.channel,
        i.audience_type,
        i.country,
        DATE_TRUNC(c.conversion_ts, MONTH)  AS month,
        COUNT(DISTINCT c.conversion_id)     AS conversions,
        SUM(c.revenue_eur)                  AS revenue_eur
    FROM `prod.events.conversions` c
    -- Last-touch attribution: link conversion to most recent impression within window
    INNER JOIN (
        SELECT
            user_id,
            channel,
            audience_type,
            country,
            MAX(impression_ts) AS last_impression_ts
        FROM `prod.media.impressions`
        WHERE impression_ts BETWEEN '2025-07-01' AND '2025-09-30'
        GROUP BY 1, 2, 3, 4
    ) i
        ON  c.user_id = i.user_id
        AND c.conversion_ts BETWEEN i.last_impression_ts
                                AND TIMESTAMP_ADD(i.last_impression_ts, INTERVAL 7 DAY)
    WHERE c.conversion_ts BETWEEN '2025-07-01' AND '2025-09-30'
    GROUP BY 1, 2, 3, 4
)

SELECT
    s.channel,
    s.audience_type,
    s.country,
    s.month,
    s.total_spend_eur,
    s.reached_users,
    COALESCE(c.conversions, 0)                              AS attributed_conversions,
    COALESCE(c.revenue_eur, 0)                              AS attributed_revenue_eur,
    SAFE_DIVIDE(s.total_spend_eur, c.conversions)           AS reported_cpa,
    SAFE_DIVIDE(c.revenue_eur, s.total_spend_eur)           AS reported_roas,
    SAFE_DIVIDE(c.conversions, s.reached_users)             AS reported_cvr
FROM impression_spend s
LEFT JOIN attributed_conversions c USING (channel, audience_type, country, month)
ORDER BY s.month, s.total_spend_eur DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Baseline intent signal — pre-exposure behaviour by audience segment
--    Purpose: show that retargeting audiences have high organic intent
--    regardless of ad exposure (motivates causal adjustment)
-- ─────────────────────────────────────────────────────────────────────────────
WITH exposed_users AS (
    SELECT DISTINCT
        i.user_id,
        i.audience_type,
        i.channel
    FROM `prod.media.impressions` i
    WHERE i.impression_ts BETWEEN '2025-07-01' AND '2025-09-30'
),

user_features AS (
    SELECT
        user_id,
        n_prior_purchases,
        n_organic_sessions_30d,
        days_since_last_visit,
        email_subscriber,
        loyalty_tier
    FROM `prod.crm.user_features`
)

SELECT
    e.audience_type,
    e.channel,
    COUNT(DISTINCT e.user_id)                           AS user_count,
    AVG(f.n_prior_purchases)                            AS avg_prior_purchases,
    AVG(f.n_organic_sessions_30d)                       AS avg_organic_sessions,
    AVG(f.days_since_last_visit)                        AS avg_days_since_visit,
    COUNTIF(f.email_subscriber) / COUNT(*)              AS pct_email_subscribers,
    COUNTIF(f.loyalty_tier IN ('gold', 'platinum'))
        / COUNT(*)                                      AS pct_high_loyalty
FROM exposed_users e
LEFT JOIN user_features f USING (user_id)
GROUP BY 1, 2
ORDER BY avg_prior_purchases DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Frequency analysis — impressions per user by audience type
--    Purpose: identify over-capping and waste above optimal frequency band
-- ─────────────────────────────────────────────────────────────────────────────
WITH user_frequency AS (
    SELECT
        user_id,
        audience_type,
        channel,
        country,
        COUNT(impression_id)    AS impression_count,
        SUM(spend_eur)          AS user_spend_eur
    FROM `prod.media.impressions`
    WHERE impression_ts BETWEEN '2025-07-01' AND '2025-09-30'
    GROUP BY 1, 2, 3, 4
),

conversions_30d AS (
    SELECT DISTINCT user_id
    FROM `prod.events.conversions`
    WHERE conversion_ts BETWEEN '2025-07-01' AND '2025-09-30'
),

frequency_bands AS (
    SELECT
        *,
        CASE
            WHEN impression_count BETWEEN 1  AND 2  THEN '01-02'
            WHEN impression_count BETWEEN 3  AND 5  THEN '03-05'
            WHEN impression_count BETWEEN 6  AND 9  THEN '06-09'
            WHEN impression_count BETWEEN 10 AND 14 THEN '10-14'
            WHEN impression_count BETWEEN 15 AND 20 THEN '15-20'
            ELSE '21+'
        END AS freq_band
    FROM user_frequency
)

SELECT
    freq_band,
    audience_type,
    channel,
    COUNT(DISTINCT fb.user_id)                          AS users,
    COUNTIF(c.user_id IS NOT NULL)                      AS converters,
    SAFE_DIVIDE(
        COUNTIF(c.user_id IS NOT NULL),
        COUNT(DISTINCT fb.user_id)
    )                                                   AS cvr,
    SUM(user_spend_eur)                                 AS total_spend_eur
FROM frequency_bands fb
LEFT JOIN conversions_30d c USING (user_id)
GROUP BY 1, 2, 3
ORDER BY audience_type, channel, freq_band;
