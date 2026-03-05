-- Migration 002: Rename schema sherlock → reasoner
-- Idempotent: safe to re-run on already-migrated database

DO $$
BEGIN
    -- Case 1: sherlock schema exists → rename to reasoner
    IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'sherlock') THEN
        ALTER SCHEMA sherlock RENAME TO reasoner;
        RAISE NOTICE 'Schema sherlock renamed to reasoner';

    -- Case 2: reasoner already exists → no-op
    ELSIF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'reasoner') THEN
        RAISE NOTICE 'Schema reasoner already exists, skipping rename';

    -- Case 3: neither exists → create reasoner fresh
    ELSE
        CREATE SCHEMA IF NOT EXISTS reasoner;
        RAISE NOTICE 'Neither schema existed; created reasoner schema fresh';
    END IF;
END
$$;
