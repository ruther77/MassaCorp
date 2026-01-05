-- 🔑 3) sso_sessions — traçabilité des connexions SSO
CREATE TABLE sso_sessions (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    provider_name TEXT NOT NULL,
    external_session_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX sso_sessions_user_idx
    ON sso_sessions (user_id);

CREATE INDEX sso_sessions_tenant_idx
    ON sso_sessions (tenant_id);

CREATE INDEX sso_sessions_active_idx
    ON sso_sessions (id)
    WHERE revoked_at IS NULL;

