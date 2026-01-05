-- 🔐 2) Table permissions (permissions atomiques globales)
CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,                -- ex: read:inventory
    description TEXT,

    UNIQUE (name)
);
