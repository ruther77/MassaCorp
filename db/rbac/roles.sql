--- 🛂 1) Table roles (rôles par tenant)
CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    name TEXT NOT NULL,                -- ex: admin, manager, viewer
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, name)
);

CREATE INDEX roles_tenant_idx
    ON roles (tenant_id);

