----- TABLE login_attempts — anti-bruteforce / rate-limit (PostgreSQL)
CREATE TABLE login_attempts (
    id BIGSERIAL PRIMARY KEY,
    identifier TEXT NOT NULL,     -- email / username
    ip TEXT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success BOOLEAN NOT NULL
);

CREATE INDEX login_attempts_identifier_idx
    ON login_attempts (identifier);

CREATE INDEX login_attempts_ip_idx
    ON login_attempts (ip);

CREATE INDEX login_attempts_attempted_at_idx
    ON login_attempts (attempted_at);
    
