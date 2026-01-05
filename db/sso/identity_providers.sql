🏢 1) identity_providers — configuration SSO par tenant
CREATE TABLE identity_providers (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    provider_type TEXT NOT NULL,     -- 'oidc' | 'saml'
    provider_name TEXT NOT NULL,     -- 'google' | 'microsoft' | 'okta' | etc.
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- OIDC
    client_id TEXT,
    client_secret TEXT,
    issuer_url TEXT,

    -- SAML
    saml_entity_id TEXT,
    saml_metadata XML,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, provider_name)
);

CREATE INDEX identity_providers_tenant_idx
    ON identity_providers (tenant_id);

CREATE INDEX identity_providers_enabled_idx
    ON identity_providers (enabled);
