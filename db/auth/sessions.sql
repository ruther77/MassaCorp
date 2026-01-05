----- TABLES SESSIONS -----

CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip TEXT,
    user_agent TEXT,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX sessions_user_id_idx ON sessions (user_id);
CREATE INDEX sessions_tenant_id_idx ON sessions (tenant_id);
CREATE INDEX sessions_revoked_at_idx ON sessions (revoked_at);

CREATE INDEX sessions_active_idx
  ON sessions (id)
  WHERE revoked_at IS NULL;

CREATE INDEX sessions_tenant_active_idx
  ON sessions (tenant_id, user_id)
  WHERE revoked_at IS NULL;

