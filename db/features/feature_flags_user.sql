-- 👤 5) Table feature_flags_user
CREATE TABLE feature_flags_user (
    feature_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    enabled BOOLEAN NOT NULL,

    PRIMARY KEY (feature_id, user_id),

    CONSTRAINT feature_flags_user_feature_fk
        FOREIGN KEY (feature_id)
        REFERENCES features (id)
        ON DELETE CASCADE
);

CREATE INDEX feature_flags_user_idx
    ON feature_flags_user (user_id);

