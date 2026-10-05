-- Step 2. Where is the drop? Compare "before" (4 weeks) vs "after" (2 incident weeks)
-- by segment, with each segment's share of signups (mix) and its retention (rate).
WITH periods AS (
    SELECT *,
           CASE WHEN cohort_week <  DATE '2026-07-06' THEN 'before'
                WHEN cohort_week <  DATE '2026-07-20' THEN 'after'
           END AS period
    FROM freshcart.user_metrics
    WHERE cohort_week >= DATE '2026-06-08'          -- 4 clean weeks before
),
seg AS (
    SELECT period, 'platform' AS dim, platform AS segment, count(*) AS n,
           avg(retained_d7::int) AS ret
    FROM periods WHERE period IS NOT NULL GROUP BY 1, 3
    UNION ALL
    SELECT period, 'channel', channel, count(*), avg(retained_d7::int)
    FROM periods WHERE period IS NOT NULL GROUP BY 1, 3
)
SELECT
    dim, segment,
    round(100.0 * max(n)   FILTER (WHERE period = 'before')
          / sum(max(n) FILTER (WHERE period = 'before')) OVER (PARTITION BY dim), 1) AS share_before_pct,
    round(100.0 * max(n)   FILTER (WHERE period = 'after')
          / sum(max(n) FILTER (WHERE period = 'after'))  OVER (PARTITION BY dim), 1) AS share_after_pct,
    round(100.0 * max(ret) FILTER (WHERE period = 'before'), 1)  AS ret_before_pct,
    round(100.0 * max(ret) FILTER (WHERE period = 'after'),  1)  AS ret_after_pct,
    round(100.0 * (max(ret) FILTER (WHERE period = 'after')
                 - max(ret) FILTER (WHERE period = 'before')), 1) AS delta_pp
FROM seg
GROUP BY dim, segment
ORDER BY dim, delta_pp;
