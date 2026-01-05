-- db/sql/00_init.sql

\i db/sql/auth/revoked_tokens.sql
\i db/sql/auth/sessions.sql
\i db/sql/auth/refresh_tokens.sql

\i db/sql/audit/audit_log.sql
\i db/sql/security/login_attempts.sql

\i db/sql/mfa/mfa_secrets.sql
\i db/sql/mfa/mfa_recovery_codes.sql

\i db/sql/sso/identity_providers.sql
\i db/sql/sso/user_identities.sql
\i db/sql/sso/sso_sessions.sql

\i db/sql/api_keys/api_keys.sql
\i db/sql/api_keys/api_key_usage.sql

\i db/sql/rbac/roles.sql
\i db/sql/rbac/permissions.sql
\i db/sql/rbac/role_permissions.sql
\i db/sql/rbac/user_roles.sql
\i db/sql/rbac/api_key_roles.sql
\i db/sql/rbac/role_hierarchy.sql

\i db/sql/features/features.sql
\i db/sql/features/feature_flags_global.sql
\i db/sql/features/feature_flags_tenant.sql
\i db/sql/features/feature_flags_role.sql
\i db/sql/features/feature_flags_user.sql

