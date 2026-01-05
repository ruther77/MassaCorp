-- db/sql/00_init_flat.sql
-- Initial schema - SaaS Auth / Security / RBAC / Features
-- Compatible Alembic, transactionnel, ordre FK correct

BEGIN;

-- =====================================================
-- AUTH / SECURITY CORE
-- =====================================================

-- revoked_tokens
CREATE TABLE revoked_tokens (
  jti TEXT PRIMARY KEY,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX revoked_tokens_expires_at_idx
  ON revoked_tokens (expires_at);

-- Index sur expires_at pour filtrer les tokens actifs (filtrage en runtime)
CREATE INDEX revoked_tokens_expires_idx
  ON revoked_tokens (expires_at DESC);


-- sessions
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


-- refresh_tokens (FK -> sessions)
CREATE TABLE refresh_tokens (
    jti TEXT PRIMARY KEY,
    session_id UUID NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    used_at TIMESTAMPTZ,
    replaced_by_jti TEXT,
    CONSTRAINT refresh_tokens_session_fk
        FOREIGN KEY (session_id)
        REFERENCES sessions (id)
        ON DELETE CASCADE
);

CREATE INDEX refresh_tokens_session_id_idx ON refresh_tokens (session_id);
CREATE INDEX refresh_tokens_expires_at_idx ON refresh_tokens (expires_at);
CREATE INDEX refresh_tokens_used_at_idx ON refresh_tokens (used_at);

CREATE INDEX refresh_tokens_used_not_null_idx
  ON refresh_tokens (jti)
  WHERE used_at IS NOT NULL;

-- Index pour les tokens actifs (filtrage used_at IS NULL en runtime)
CREATE INDEX refresh_tokens_active_session_idx
  ON refresh_tokens (session_id, expires_at)
  WHERE used_at IS NULL;


-- =====================================================
-- AUDIT / ANTI-BRUTEFORCE
-- =====================================================

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


CREATE TABLE login_attempts (
    id BIGSERIAL PRIMARY KEY,
    identifier TEXT NOT NULL,
    ip TEXT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success BOOLEAN NOT NULL
);

CREATE INDEX login_attempts_identifier_idx ON login_attempts (identifier);
CREATE INDEX login_attempts_ip_idx ON login_attempts (ip);
CREATE INDEX login_attempts_attempted_at_idx ON login_attempts (attempted_at);


-- =====================================================
-- MFA
-- =====================================================

CREATE TABLE mfa_secrets (
    user_id BIGINT PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    secret TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX mfa_secrets_tenant_idx ON mfa_secrets (tenant_id);


CREATE TABLE mfa_recovery_codes (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    code_hash TEXT NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX mfa_recovery_codes_user_idx ON mfa_recovery_codes (user_id);
CREATE INDEX mfa_recovery_codes_used_at_idx ON mfa_recovery_codes (used_at);


-- =====================================================
-- SSO
-- =====================================================

CREATE TABLE identity_providers (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    provider_type TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    client_id TEXT,
    client_secret TEXT,
    issuer_url TEXT,
    saml_entity_id TEXT,
    saml_metadata XML,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, provider_name)
);

CREATE INDEX identity_providers_tenant_idx ON identity_providers (tenant_id);
CREATE INDEX identity_providers_enabled_idx ON identity_providers (enabled);


CREATE TABLE user_identities (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    provider_name TEXT NOT NULL,
    external_subject TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, provider_name, external_subject)
);

CREATE INDEX user_identities_user_idx ON user_identities (user_id);
CREATE INDEX user_identities_tenant_idx ON user_identities (tenant_id);


CREATE TABLE sso_sessions (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    provider_name TEXT NOT NULL,
    external_session_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX sso_sessions_user_idx ON sso_sessions (user_id);
CREATE INDEX sso_sessions_tenant_idx ON sso_sessions (tenant_id);

CREATE INDEX sso_sessions_active_idx
  ON sso_sessions (id)
  WHERE revoked_at IS NULL;


-- =====================================================
-- API KEYS
-- =====================================================

CREATE TABLE api_keys (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    scopes TEXT[] NOT NULL,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    UNIQUE (tenant_id, name)
);

CREATE INDEX api_keys_key_hash_idx ON api_keys (key_hash);
CREATE INDEX api_keys_active_tenant_idx
  ON api_keys (tenant_id)
  WHERE revoked_at IS NULL;
CREATE INDEX api_keys_expires_at_idx ON api_keys (expires_at);
CREATE INDEX api_keys_last_used_at_idx ON api_keys (last_used_at);


CREATE TABLE api_key_usage (
    id BIGSERIAL PRIMARY KEY,
    api_key_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    ip TEXT,
    endpoint TEXT,
    method TEXT,
    used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT api_key_usage_fk
        FOREIGN KEY (api_key_id)
        REFERENCES api_keys (id)
        ON DELETE CASCADE
);

CREATE INDEX api_key_usage_key_idx ON api_key_usage (api_key_id);
CREATE INDEX api_key_usage_tenant_idx ON api_key_usage (tenant_id);
CREATE INDEX api_key_usage_used_at_idx ON api_key_usage (used_at);


-- =====================================================
-- RBAC
-- =====================================================

CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX roles_tenant_idx ON roles (tenant_id);


CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    UNIQUE (name)
);


CREATE TABLE role_permissions (
    role_id BIGINT NOT NULL,
    permission_id BIGINT NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    CONSTRAINT role_permissions_role_fk
        FOREIGN KEY (role_id)
        REFERENCES roles (id)
        ON DELETE CASCADE,
    CONSTRAINT role_permissions_permission_fk
        FOREIGN KEY (permission_id)
        REFERENCES permissions (id)
        ON DELETE CASCADE
);


CREATE TABLE user_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT user_roles_role_fk
        FOREIGN KEY (role_id)
        REFERENCES roles (id)
        ON DELETE CASCADE
);

CREATE INDEX user_roles_user_idx ON user_roles (user_id);
CREATE INDEX user_roles_tenant_idx ON user_roles (tenant_id);


CREATE TABLE api_key_roles (
    api_key_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    PRIMARY KEY (api_key_id, role_id),
    CONSTRAINT api_key_roles_key_fk
        FOREIGN KEY (api_key_id)
        REFERENCES api_keys (id)
        ON DELETE CASCADE,
    CONSTRAINT api_key_roles_role_fk
        FOREIGN KEY (role_id)
        REFERENCES roles (id)
        ON DELETE CASCADE
);

CREATE INDEX api_key_roles_key_idx ON api_key_roles (api_key_id);
CREATE INDEX api_key_roles_tenant_idx ON api_key_roles (tenant_id);


CREATE TABLE role_hierarchy (
    parent_role_id BIGINT NOT NULL,
    child_role_id BIGINT NOT NULL,
    PRIMARY KEY (parent_role_id, child_role_id),
    CONSTRAINT role_hierarchy_parent_fk
        FOREIGN KEY (parent_role_id)
        REFERENCES roles (id)
        ON DELETE CASCADE,
    CONSTRAINT role_hierarchy_child_fk
        FOREIGN KEY (child_role_id)
        REFERENCES roles (id)
        ON DELETE CASCADE
);

CREATE INDEX role_permissions_role_idx ON role_permissions (role_id);
CREATE INDEX role_permissions_permission_idx ON role_permissions (permission_id);


-- =====================================================
-- FEATURE FLAGS
-- =====================================================

CREATE TABLE features (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (key)
);


CREATE TABLE feature_flags_global (
    feature_id BIGINT PRIMARY KEY,
    enabled BOOLEAN NOT NULL,
    CONSTRAINT feature_flags_global_feature_fk
        FOREIGN KEY (feature_id)
        REFERENCES features (id)
        ON DELETE CASCADE
);


CREATE TABLE feature_flags_tenant (
    feature_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    enabled BOOLEAN NOT NULL,
    PRIMARY KEY (feature_id, tenant_id),
    CONSTRAINT feature_flags_tenant_feature_fk
        FOREIGN KEY (feature_id)
        REFERENCES features (id)
        ON DELETE CASCADE
);

CREATE INDEX feature_flags_tenant_idx ON feature_flags_tenant (tenant_id);


CREATE TABLE feature_flags_role (
    feature_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    enabled BOOLEAN NOT NULL,
    PRIMARY KEY (feature_id, role_id),
    CONSTRAINT feature_flags_role_feature_fk
        FOREIGN KEY (feature_id)
        REFERENCES features (id)
        ON DELETE CASCADE
);

CREATE INDEX feature_flags_role_idx ON feature_flags_role (role_id);


CREATE TABLE feature_flags_user (
    feature_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    enabled BOOLEAN NOT NULL,
    PRIMARY KEY (feature_id, user_id),
    CONSTRAINT feature_flags_user_feature_fk
        FOREIGN KEY (feature_id)
        REFERENCES features (id)
        ON DELETE CASCADE
);

CREATE INDEX feature_flags_user_idx ON feature_flags_user (user_id);


COMMIT;

