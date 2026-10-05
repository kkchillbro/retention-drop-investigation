-- Run from the repo root:  psql -d <db> -f sql/02_load.sql
\copy freshcart.users  FROM 'data/users.csv'  WITH (FORMAT csv, HEADER true)
\copy freshcart.events FROM 'data/events.csv' WITH (FORMAT csv, HEADER true)
ANALYZE freshcart.users;
ANALYZE freshcart.events;
