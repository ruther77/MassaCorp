-- 🛂 4) Table feature_flags_role
CREATE TABLE feature_flags_role (
    feature_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    enabled BOOLEAN NOT NULL,

    PRIMARY KEY (feature_id, role_id),

    CONSTRAINT feature_flags_role_feature_fk
        FOREIGN KEY (feature_id)
        REFERENCES features (id)
        ON DELETE CASCADE
);

CREATE INDEX feature_flags_role_idx
    ON feature_flags_role (role_id);

