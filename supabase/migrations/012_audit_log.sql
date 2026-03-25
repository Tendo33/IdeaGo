-- 012: Structured audit log for admin actions and security events.
-- Run after 011_pg_rate_limiter.sql.

CREATE TABLE IF NOT EXISTS audit_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id    text NOT NULL,
    action      text NOT NULL,
    target_type text,
    target_id   text,
    metadata    jsonb DEFAULT '{}',
    ip_address  text,
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_actor
    ON audit_log (actor_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_action
    ON audit_log (action, created_at DESC);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
-- No anon/authenticated policies: service_role only (backend writes).

-- Cleanup: delete audit entries older than 90 days.
CREATE OR REPLACE FUNCTION cleanup_audit_log(retention_days int DEFAULT 90)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    removed int;
BEGIN
    DELETE FROM audit_log
    WHERE created_at < now() - make_interval(days => retention_days);
    GET DIAGNOSTICS removed = ROW_COUNT;
    RETURN removed;
END;
$$;
