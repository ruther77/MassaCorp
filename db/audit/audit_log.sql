--- TABLES AUDIT LOG ----

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id BIGINT,
    tenant_id BIGINT,
    session_id UUID,
    ip TEXT,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX audit_log_event_type_idx ON audit_log (event_type);
CREATE INDEX audit_log_user_idx ON audit_log (user_id);
CREATE INDEX audit_log_tenant_idx ON audit_log (tenant_id);
CREATE INDEX audit_log_created_at_idx ON audit_log (created_at);

