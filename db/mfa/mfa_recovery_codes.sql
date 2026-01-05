----  TABLE mfa_recovery_codes — codes de secours (PostgreSQL)
CREATE TABLE mfa_recovery_codes (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    code_hash TEXT NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX mfa_recovery_codes_user_idx
    ON mfa_recovery_codes (user_id);

CREATE INDEX mfa_recovery_codes_used_at_idx
    ON mfa_recovery_codes (used_at);


