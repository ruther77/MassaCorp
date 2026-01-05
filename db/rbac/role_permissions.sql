-- 🔗 3) Table role_permissions (mapping rôle ↔ permissions)
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

