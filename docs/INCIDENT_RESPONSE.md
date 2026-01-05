# Incident Response Plan

## Overview

This document outlines the incident response procedures for MassaCorp security incidents.

## Severity Classification

### P1 - Critical
- Active data breach
- Authentication bypass
- RCE exploitation
- Database compromise

**Response Time**: Immediate (within 15 minutes)

### P2 - High
- Suspected breach under investigation
- Privilege escalation
- Significant service disruption

**Response Time**: Within 1 hour

### P3 - Medium
- Failed attack attempts
- Suspicious activity patterns
- Minor service issues

**Response Time**: Within 4 hours

### P4 - Low
- Policy violations
- Audit findings
- Security improvements needed

**Response Time**: Next business day

## Response Team

| Role | Responsibility |
|------|----------------|
| **Incident Commander** | Overall coordination |
| **Security Lead** | Technical investigation |
| **DevOps Lead** | System access and logs |
| **Legal/Compliance** | Regulatory requirements |
| **Communications** | Internal/external comms |

## Response Phases

### 1. Detection & Identification (0-30 min)

- [ ] Alert received and acknowledged
- [ ] Initial severity assessment
- [ ] Incident Commander assigned
- [ ] Response team notified
- [ ] Incident ticket created

### 2. Containment (30 min - 2 hours)

**Short-term:**
- [ ] Isolate affected systems
- [ ] Block malicious IPs/users
- [ ] Preserve evidence (logs, memory dumps)
- [ ] Disable compromised credentials

**Long-term:**
- [ ] Identify attack vector
- [ ] Patch vulnerabilities
- [ ] Enhanced monitoring

### 3. Eradication (2-24 hours)

- [ ] Remove malware/backdoors
- [ ] Reset compromised credentials
- [ ] Patch all affected systems
- [ ] Verify no persistence mechanisms

### 4. Recovery (24-72 hours)

- [ ] Restore from clean backups
- [ ] Gradual service restoration
- [ ] Enhanced monitoring period
- [ ] Verify system integrity

### 5. Post-Incident (1-2 weeks)

- [ ] Root cause analysis
- [ ] Lessons learned documentation
- [ ] Security improvements implemented
- [ ] Incident report finalized
- [ ] Regulatory notifications (if required)

## Communication Templates

### Internal Notification
```
SECURITY INCIDENT - [SEVERITY]

Time Detected: [TIMESTAMP]
Incident Commander: [NAME]
Status: [INVESTIGATING/CONTAINED/RESOLVED]

Summary: [BRIEF DESCRIPTION]

Next Update: [TIME]
```

### GDPR Breach Notification (72-hour deadline)

Required for breaches affecting personal data:

1. Nature of the breach
2. Categories and number of data subjects affected
3. Contact point (DPO)
4. Likely consequences
5. Measures taken/proposed

**Authority**: CNIL (France) / Relevant DPA

## Runbooks

### Credential Compromise
```bash
# 1. Revoke all sessions for user
POST /api/v1/admin/users/{id}/revoke-sessions

# 2. Force password reset
POST /api/v1/admin/users/{id}/force-password-reset

# 3. Check audit logs
SELECT * FROM audit_log
WHERE user_id = {id}
ORDER BY created_at DESC
LIMIT 100;
```

### Suspected SQL Injection
```bash
# 1. Check slow query log
tail -f /var/log/postgresql/postgresql-*-slow.log

# 2. Review recent queries
SELECT query, calls, total_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 20;

# 3. Check for unusual patterns
grep -i "union\|select.*from\|;--" /var/log/app/*.log
```

### API Key Compromise
```bash
# 1. Revoke the key immediately
POST /api/v1/admin/api-keys/{id}/revoke

# 2. Check usage logs
SELECT * FROM api_key_usage
WHERE api_key_id = {id}
ORDER BY created_at DESC;

# 3. Notify affected tenant
```

## Evidence Preservation

### What to Collect
- Application logs
- Database query logs
- Network traffic captures
- System metrics
- User session data

### Storage
- Read-only storage
- Chain of custody documentation
- Encrypted and access-controlled
- Retention: Minimum 12 months

## Regulatory Requirements

### GDPR (EU)
- 72-hour notification to DPA for personal data breaches
- Notification to affected individuals if high risk

### SOC 2
- Document all security incidents
- Annual review of incident response procedures

## Testing

- Tabletop exercises: Quarterly
- Simulated incidents: Annually
- Plan review: After each incident

## Contacts

| Role | Contact |
|------|---------|
| Security Lead | security@massacorp.dev |
| Legal | legal@massacorp.dev |
| DPO | dpo@massacorp.dev |
| Emergency | +33 X XX XX XX XX |

---

*Last Updated: 2025-12-28*
*Next Review: 2026-03-28*
