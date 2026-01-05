---- TABLES TOKENS RELANCES -----

CREATE TABLE refresh_tokens (
    jti TEXT PRIMARY KEY,
    session_id UUID NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    used_at TIMESTAMPTZ,
    replaced_by_jti TEXT,
    CONSTRAINT refresh_tokens_session_fk
        FOREIGN KEY (session_id)
        REFERENCES sessions (id)
        ON DELETE CASCADE
);

CREATE INDEX refresh_tokens_session_id_idx ON refresh_tokens (session_id);
CREATE INDEX refresh_tokens_expires_at_idx ON refresh_tokens (expires_at);
CREATE INDEX refresh_tokens_used_at_idx ON refresh_tokens (used_at);

CREATE INDEX refresh_tokens_used_not_null_idx
  ON refresh_tokens (jti)
  WHERE used_at IS NOT NULL;

CREATE INDEX refresh_tokens_active_session_idx
  ON refresh_tokens (session_id)
  WHERE used_at IS NULL AND expires_at > NOW();

