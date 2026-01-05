
-- 🔑 1) Table api_keys
CREATE TABLE api_keys (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    name TEXT NOT NULL,                -- nom lisible (ex: "n8n-prod")
    key_hash TEXT NOT NULL,            -- hash de la clé (jamais en clair)
    scopes TEXT[] NOT NULL,             -- ex: {'read:inventory','write:orders'}
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,

    UNIQUE (tenant_id, name)
);

--🔐 2) Indexes de sécurité API Keys
-- Lookup rapide par hash
CREATE INDEX api_keys_key_hash_idx
    ON api_keys (key_hash);

-- Clés actives par tenant
CREATE INDEX api_keys_active_tenant_idx
    ON api_keys (tenant_id)
    WHERE revoked_at IS NULL;

-- Détection des clés expirées
CREATE INDEX api_keys_expires_at_idx
    ON api_keys (expires_at);

-- Audit / monitoring
CREATE INDEX api_keys_last_used_at_idx
    ON api_keys (last_used_at);
