-- Create the unleash database for arc-mystique (Unleash feature flag server).
-- Unleash's DATABASE_URL points to this database; migrations run automatically on startup.
-- This file runs on Oracle's first boot only (Postgres skips initdb if data dir exists).
-- To recreate: make oracle-nuke && make oracle-up
CREATE DATABASE unleash;
