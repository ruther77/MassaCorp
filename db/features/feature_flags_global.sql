--- 🌍 2) Table feature_flags_global
CREATE TABLE feature_flags_global (
    feature_id BIGINT PRIMARY KEY,
    enabled BOOLEAN NOT NULL,

    CONSTRAINT feature_flags_global_feature_fk
        FOREIGN KEY (feature_id)
        REFERENCES features (id)
        ON DELETE CASCADE
);
