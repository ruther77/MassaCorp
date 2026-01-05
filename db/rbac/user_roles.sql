-- 👤 4) Table user_roles (users ↔ rôles)
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

CREATE INDEX user_roles_user_idx
    ON user_roles (user_id);

CREATE INDEX user_roles_tenant_idx
    ON user_roles (tenant_id);
