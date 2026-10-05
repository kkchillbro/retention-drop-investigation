-- Step 4. Timing check: daily signup->address rate for Android, by version.
-- A step change aligned with the release date is the "smoking gun".
SELECT
    u.signup_ts::date                                     AS signup_date,
    u.app_version,
    count(*)                                              AS signups,
    round(100.0 * avg(m.address_confirmed::int), 1)       AS address_rate_pct
FROM freshcart.users u
JOIN freshcart.user_metrics m USING (user_id)
WHERE u.platform = 'android'
  AND u.signup_ts >= DATE '2026-06-29'
GROUP BY 1, 2
ORDER BY 1, 2;
