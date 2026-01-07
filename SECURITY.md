# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |

## Security Features

MassaCorp implements enterprise-grade security:

### Authentication & Authorization
- **JWT with Session Binding**: Access tokens linked to session IDs
- **MFA/TOTP**: Two-factor authentication with recovery codes
- **RBAC**: Role-based access control with granular permissions
- **OAuth2**: SSO integration (Google, Microsoft, GitHub)
- **API Keys**: M2M authentication with scopes

### Data Protection
- **Multi-tenant Isolation**: Repository-level tenant separation
- **Argon2id**: Password hashing (migrated from bcrypt)
- **Token Rotation**: Refresh token rotation on use
- **Session Management**: Active session tracking and revocation

### Infrastructure Security
- **Rate Limiting**: Redis-backed sliding window
- **HSTS**: Strict Transport Security with preload
- **CSP**: Content Security Policy headers
- **CORS**: Configured allowed origins

### Audit & Compliance
- **Audit Trail**: All sensitive actions logged
- **GDPR Support**: Data export and deletion
- **Login Attempts**: Brute-force protection

## Reporting a Vulnerability

If you discover a security vulnerability, please:

1. **Do NOT** open a public issue
2. Email security@massacorp.dev with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue.

## Security Contacts

- Security Team: security@massacorp.dev
- Emergency: +33 1 XX XX XX XX

## Acknowledgments

We thank all security researchers who responsibly disclose vulnerabilities.
