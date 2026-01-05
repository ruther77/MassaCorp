--- 🏢 3) Table feature_flags_tenant
CREATE TABLE feature_flags_tenant (
    feature_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,
    enabled BOOLEAN NOT NULL,

    PRIMARY KEY (feature_id, tenant_id),

    CONSTRAINT feature_flags_tenant_feature_fk
        FOREIGN KEY (feature_id)
        REFERENCES features (id)
        ON DELETE CASCADE
);

CREATE INDEX feature_flags_tenant_idx
    ON feature_flags_tenant (tenant_id);

