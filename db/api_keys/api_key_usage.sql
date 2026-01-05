--- 🧩 3) Table api_key_usage (audit & rate-limit)
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

CREATE INDEX api_key_usage_key_idx
    ON api_key_usage (api_key_id);

CREATE INDEX api_key_usage_tenant_idx
    ON api_key_usage (tenant_id);

CREATE INDEX api_key_usage_used_at_idx
    ON api_key_usage (used_at);

-- 🔄 4) Rotation & révocation (support SQL)
-- Révoquer une clé
UPDATE api_keys
SET revoked_at = NOW()
WHERE id = :api_key_id;
