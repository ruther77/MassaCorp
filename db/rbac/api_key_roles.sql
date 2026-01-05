-- 🔑 5) Table api_key_roles (API Keys ↔ rôles)
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

CREATE INDEX api_key_roles_key_idx
    ON api_key_roles (api_key_id);

CREATE INDEX api_key_roles_tenant_idx
    ON api_key_roles (tenant_id);
