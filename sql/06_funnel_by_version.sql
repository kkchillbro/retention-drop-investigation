-- Step 3. Drill down: step-by-step onboarding conversion by platform x app version.
-- Only cohorts from the incident window and later, so all versions are present.
SELECT
    platform,
    app_version,
    count(*)                                                        AS signups,
    round(100.0 * avg(address_confirmed::int), 1)                   AS signup_to_address_pct,
    round(100.0 * sum(payment_added::int)
          / nullif(sum(address_confirmed::int), 0), 1)              AS address_to_payment_pct,
    round(100.0 * sum(first_order::int)
          / nullif(sum(payment_added::int), 0), 1)                  AS payment_to_order_pct,
    round(100.0 * avg(retained_d7::int), 1)                         AS d7_retention_pct
FROM freshcart.user_metrics
WHERE cohort_week >= DATE '2026-07-06'
GROUP BY platform, app_version
HAVING count(*) >= 300
ORDER BY platform, app_version;
