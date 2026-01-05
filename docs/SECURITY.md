# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in MassaCorp, please report it responsibly.

### Contact

- **Email**: security@massacorp.dev
- **PGP Key**: Available at https://massacorp.dev/.well-known/security.txt

### What to Include

1. **Description** of the vulnerability
2. **Steps to reproduce** the issue
3. **Potential impact** assessment
4. **Suggested fix** (optional but appreciated)

### Response Timeline

| Stage | Timeline |
|-------|----------|
| Acknowledgment | Within 24 hours |
| Initial Assessment | Within 72 hours |
| Status Update | Weekly until resolved |
| Fix Release | Depends on severity |

### Severity Levels

| Level | Description | Target Resolution |
|-------|-------------|-------------------|
| Critical | RCE, Auth bypass, Data breach | 24-48 hours |
| High | Privilege escalation, XSS, SQLi | 1 week |
| Medium | Information disclosure, CSRF | 2 weeks |
| Low | Best practice violations | Next release |

## Security Measures

### Authentication
- JWT tokens with short expiration (15 minutes)
- Refresh token rotation
- MFA support (TOTP)
- Bcrypt password hashing (cost factor 12)

### Authorization
- Role-Based Access Control (RBAC)
- Row-Level Security (RLS) for multi-tenant isolation
- API key authentication for M2M

### Data Protection
- TLS 1.3 in transit
- Encryption at rest (database level)
- PII handling per GDPR requirements

### Monitoring
- Audit logging of all security events
- Brute-force protection with progressive lockout
- Real-time alerting via Prometheus/Alertmanager

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x.x   | Yes       |
| < 1.0   | No        |

## Security Headers

All responses include:
- `Strict-Transport-Security`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy`
- `Referrer-Policy`

## Dependency Management

- Weekly automated dependency updates (Dependabot)
- Security scanning with Bandit and Safety
- Pre-commit hooks for code review

## Incident Response

See [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md) for our incident response plan.
