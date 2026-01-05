
-------- TABLE TOKENS REJETES ---------

CREATE TABLE revoked_tokens (
  jti TEXT PRIMARY KEY,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX revoked_tokens_expires_at_idx
  ON revoked_tokens (expires_at);

CREATE INDEX revoked_tokens_active_idx
  ON revoked_tokens (jti)
  WHERE expires_at > NOW();

