-- 🎛️ 1) Table features — catalogue des fonctionnalités
CREATE TABLE features (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL,                 -- ex: 'export_excel'
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (key)
);
