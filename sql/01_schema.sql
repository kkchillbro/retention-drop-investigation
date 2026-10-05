-- Schema for the FreshCart retention investigation (PostgreSQL 14+)
DROP SCHEMA IF EXISTS freshcart CASCADE;
CREATE SCHEMA freshcart;

CREATE TABLE freshcart.users (
    user_id      BIGINT PRIMARY KEY,
    signup_ts    TIMESTAMP NOT NULL,
    platform     TEXT NOT NULL,          -- ios / android / web
    app_version  TEXT NOT NULL,
    channel      TEXT NOT NULL,          -- acquisition channel
    city         TEXT NOT NULL
);

CREATE TABLE freshcart.events (
    event_id    BIGINT PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES freshcart.users (user_id),
    event_ts    TIMESTAMP NOT NULL,
    event_name  TEXT NOT NULL            -- signup / address_confirmed / payment_added / first_order / session
);

CREATE INDEX ON freshcart.events (user_id, event_name, event_ts);
