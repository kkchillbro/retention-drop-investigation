-- One row per user: cohort week, segments, funnel flags and D7 (week-2) retention.
-- Retention definition: >= 1 session on days 7..13 after signup.
CREATE OR REPLACE VIEW freshcart.user_metrics AS
SELECT
    u.user_id,
    date_trunc('week', u.signup_ts)::date                         AS cohort_week,
    u.platform,
    u.app_version,
    u.channel,
    u.city,
    bool_or(e.event_name = 'address_confirmed')                   AS address_confirmed,
    bool_or(e.event_name = 'payment_added')                       AS payment_added,
    bool_or(e.event_name = 'first_order')                         AS first_order,
    bool_or(e.event_name = 'session'
            AND e.event_ts >= u.signup_ts + interval '7 days'
            AND e.event_ts <  u.signup_ts + interval '14 days')   AS retained_d7
FROM freshcart.users u
LEFT JOIN freshcart.events e USING (user_id)
GROUP BY u.user_id;
