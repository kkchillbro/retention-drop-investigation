-- Step 1. Confirm the problem: weekly D7 retention and signups.
SELECT
    cohort_week,
    count(*)                                              AS signups,
    round(100.0 * avg(retained_d7::int), 1)               AS d7_retention_pct,
    round(100.0 * avg(first_order::int), 1)               AS first_order_pct
FROM freshcart.user_metrics
GROUP BY cohort_week
ORDER BY cohort_week;
