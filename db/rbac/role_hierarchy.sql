-- 🧠 6) Option avancée (facultative) — héritage de rôles
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

-- 🔍 7) Indexes de sécurité RBAC
CREATE INDEX role_permissions_role_idx
    ON role_permissions (role_id);

CREATE INDEX role_permissions_permission_idx
    ON role_permissions (permission_id);

