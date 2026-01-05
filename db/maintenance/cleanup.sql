DELETE FROM login_attempts
WHERE attempted_at < NOW() - INTERVAL '30 days';

DELETE FROM audit_log
WHERE created_at < NOW() - INTERVAL '12 months';

DELETE FROM sso_sessions
WHERE revoked_at IS NOT NULL
  AND revoked_at < NOW() - INTERVAL '90 days';

DELETE FROM api_keys
WHERE expires_at IS NOT NULL
  AND expires_at < NOW();
