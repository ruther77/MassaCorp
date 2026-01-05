-- 👤 2) user_identities — lien user ↔ provider externe
CREATE TABLE user_identities (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    provider_name TEXT NOT NULL,
    external_subject TEXT NOT NULL,      -- sub OIDC / NameID SAML
    email TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, provider_name, external_subject)
);

CREATE INDEX user_identities_user_idx
    ON user_identities (user_id);

CREATE INDEX user_identities_tenant_idx
    ON user_identities (tenant_id);
