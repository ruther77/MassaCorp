----- TABLE mfa_secrets — MFA TOTP (PostgreSQL)
CREATE TABLE mfa_secrets (
    user_id BIGINT PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    secret TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX mfa_secrets_tenant_idx
    ON mfa_secrets (tenant_id);


