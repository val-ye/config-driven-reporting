-- One dimensional model shared by every client.
-- Clients differ only in configuration (config/clients.yaml), never in tables.

CREATE OR REPLACE TABLE dim_client AS
SELECT DISTINCT client FROM raw_daily
UNION SELECT DISTINCT client FROM raw_weekly;

CREATE OR REPLACE TABLE dim_channel AS
SELECT DISTINCT channel FROM raw_daily
UNION SELECT DISTINCT channel FROM raw_weekly;

CREATE OR REPLACE TABLE dim_campaign AS
SELECT DISTINCT campaign, client, channel FROM raw_daily
UNION SELECT DISTINCT campaign, client, channel FROM raw_weekly;

CREATE OR REPLACE TABLE dim_date AS
SELECT DISTINCT
    CAST(date AS DATE)            AS date,
    dayofweek(CAST(date AS DATE)) AS dow   -- Sunday = 0
FROM raw_daily;

-- Grain: one row per client, campaign, channel and day.
-- Only additive measures live here. Ratios (CPA, ROAS, conversion rate ...)
-- are computed at query time as sum(numerator) / sum(denominator), so they
-- are correct at any grain: day, week, channel or the whole period.
-- A measure a client does not send is NULL, not zero: zero would mean
-- "we measured it and it was zero", which is a different statement.
CREATE OR REPLACE TABLE fact_daily_performance AS
SELECT
    CAST(date AS DATE)                AS date,
    client,
    campaign,
    channel,
    CAST(spend       AS DOUBLE)       AS spend,
    CAST(impressions AS BIGINT)       AS impressions,
    CAST(sessions    AS BIGINT)       AS sessions,
    CAST(conversions AS BIGINT)       AS conversions,
    CAST(revenue     AS DOUBLE)       AS revenue
FROM raw_daily;

-- Some sources only deliver weekly totals. They get their own fact table at
-- their own grain (one row per client, campaign, channel and week), sharing
-- the same dimensions and the same additive measures. We never spread a
-- weekly number across days: that would invent detail nobody measured.
-- Reports combine the two tables at the coarser grain (week), which works
-- because every measure is additive and every ratio is computed after the sum.
CREATE OR REPLACE TABLE fact_weekly_performance AS
SELECT
    CAST(week_start AS DATE)          AS week_start,
    client,
    campaign,
    channel,
    CAST(spend       AS DOUBLE)       AS spend,
    CAST(impressions AS BIGINT)       AS impressions,
    CAST(sessions    AS BIGINT)       AS sessions,
    CAST(conversions AS BIGINT)       AS conversions,
    CAST(revenue     AS DOUBLE)       AS revenue
FROM raw_weekly;
