-- Runs once when the Postgres container's volume is first created.
-- The pytest suite migrates and truncates this database freely, so it is
-- kept separate from the `explorer` database the API serves.
CREATE DATABASE explorer_test;
