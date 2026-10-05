-- H0 / H4 checks used in the hypothesis tree.

-- H0: is it a tracking problem? Weekly session volume and sessions per active user
-- should have no gaps or sudden breaks around the release date.
SELECT date_trunc('week', event_ts)::date                                  AS week,
       count(*) FILTER (WHERE event_name = 'session')                       AS sessions,
       round(count(*) FILTER (WHERE event_name = 'session')::numeric
             / count(DISTINCT user_id), 2)                                  AS sessions_per_active_user
FROM freshcart.events
GROUP BY 1
ORDER BY 1;

-- H4: is it one market? D7 retention by city, before vs incident weeks.
SELECT city,
       round(100.0 * avg(retained_d7::int) FILTER (WHERE cohort_week BETWEEN '2026-06-08' AND '2026-06-29'), 1) AS before_pct,
       round(100.0 * avg(retained_d7::int) FILTER (WHERE cohort_week BETWEEN '2026-07-06' AND '2026-07-13'), 1) AS incident_pct
FROM freshcart.user_metrics
GROUP BY city
ORDER BY city;
