-- Bootstrap schema_migrations table.
-- Used by the Cortex health probe to verify the database schema is initialized.
-- This table is populated by database migration tools (e.g. golang-migrate) on
-- subsequent application migrations.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version bigint  NOT NULL PRIMARY KEY,
    dirty   boolean NOT NULL
);
