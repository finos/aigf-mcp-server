# Security Policy

## 🛡️ Security Overview

This AI Governance MCP Server takes security seriously and follows enterprise-grade security practices to protect users and maintain the integrity of the AI governance framework.

## 🔒 Security Features

### Built-in Security Controls

- **Input Validation**: All user inputs validated with Pydantic schemas
- **HTTP Security**: Secure HTTP client with timeout controls and redirect protection
- **Dependency Security**: Regular vulnerability scanning with pip-audit
- **Secret Protection**: Gitleaks scanning prevents credential exposure
- **Static Analysis**: CodeQL security analysis for code vulnerabilities

### Security Scanning Infrastructure

- ✅ **CodeQL Static Analysis**: Weekly automated scans for security vulnerabilities
- ✅ **Gitleaks Secret Scanning**: Daily scans for exposed credentials and API keys
- ✅ **pip-audit Vulnerability Tracking**: Continuous monitoring of dependency vulnerabilities
- ✅ **Bandit Security Linting**: Python security issue detection in pre-commit hooks
- ✅ **CycloneDX SBOM Generation**: Software Bill of Materials for supply chain transparency

## 🚨 Reporting Security Vulnerabilities

**IMPORTANT**: Do not report security vulnerabilities through public GitHub issues.

### For Security Vulnerabilities

1. **GitHub Security Advisory**: Create a [Security Advisory](https://github.com/hugo-calderon/finos-mcp-server/security/advisories) for responsible disclosure
3. **Include**:
   - Detailed description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact assessment
   - Suggested mitigation (if available)
4. **Response Time**: Best effort acknowledgment within 72 hours
5. **Disclosure**: Allow reasonable time for response before public disclosure

### Vulnerability Report Template

```
Subject: SECURITY: AI Governance MCP Server - [Brief Description]

## Vulnerability Details
- **Component**: [Affected component or module]
- **Severity**: [Critical/High/Medium/Low]
- **Attack Vector**: [How the vulnerability can be exploited]

## Description
[Detailed description of the vulnerability]

## Reproduction Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Impact Assessment
[Potential consequences and affected systems]

## Suggested Mitigation
[If you have suggestions for fixing the issue]

## Contact Information
- **Name**: [Your name]
- **Organization**: [Your organization, if applicable]
- **Email**: [Contact email]
```

## 🔐 Security Best Practices for Contributors

### Code Security Requirements

All contributions must follow these security practices:

#### 1. No Secrets in Code
```python
# ❌ BAD: Hardcoded secrets
API_KEY = "sk-1234567890abcdef"  # pragma: allowlist secret

# ✅ GOOD: Environment variables
import os
API_KEY = os.getenv("API_KEY")
```

#### 2. Input Validation
```python
# ✅ GOOD: Pydantic validation
from pydantic import BaseModel, Field, validator

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)

    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()
```

#### 3. Secure HTTP Practices
```python
# ✅ GOOD: Secure HTTP client usage
async with httpx.AsyncClient(
    timeout=30.0,
    follow_redirects=False,  # Prevent redirect attacks
    verify=True              # Verify SSL certificates
) as client:
    response = await client.get(url)
    response.raise_for_status()
```

#### 4. Error Handling
```python
# ✅ GOOD: Secure error handling
try:
    result = await process_user_input(data)
    return result
except ValidationError as e:
    # Log error without exposing internals
    logger.warning("Invalid input received", extra={"error_type": "validation"})
    raise HTTPException(status_code=400, detail="Invalid input")
except Exception as e:
    # Never expose internal error details to users
    logger.error("Internal processing error", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

### Pre-commit Security Hooks

All code changes are automatically validated with:

- **bandit**: Python security linter
- **gitleaks**: Secret detection
- **pip-audit**: Dependency vulnerability scanning
- **detect-secrets**: Additional secret pattern detection

## 🔍 Security Scanning Results

### Current Security Status

As of the latest scan:

- ✅ **CodeQL**: No critical or high severity issues
- ✅ **Gitleaks**: No secrets detected
- ✅ **pip-audit**: No known vulnerabilities in dependencies
- ✅ **Bandit**: No security issues in Python code

### Continuous Monitoring

Security scans run automatically:

- **CodeQL**: Weekly scheduled scans
- **Gitleaks**: Daily secret scanning
- **pip-audit**: On every dependency change
- **Pre-commit hooks**: On every commit

## 📋 Security Checklist for Contributors

Before submitting code:

- [ ] No hardcoded secrets, passwords, or API keys
- [ ] All user inputs validated with Pydantic schemas
- [ ] Error messages don't expose internal system details
- [ ] HTTP requests use secure client configuration
- [ ] Dependencies are up-to-date with no known vulnerabilities
- [ ] Pre-commit security hooks pass without issues
- [ ] New code includes appropriate security tests

## 🚀 Deployment Security

### Environment Variables

Secure configuration management:

```bash
# Development
FINOS_MCP_LOG_LEVEL=DEBUG
FINOS_MCP_DEBUG_MODE=true

# Production
FINOS_MCP_LOG_LEVEL=WARNING
FINOS_MCP_DEBUG_MODE=false
FINOS_MCP_HTTP_TIMEOUT=60
```

### Network Security

- **HTTPS Only**: All external communications use HTTPS
- **Timeout Controls**: HTTP requests have strict timeout limits
- **Redirect Protection**: Automatic redirects are disabled
- **Certificate Validation**: SSL certificates are always verified

## 🔄 Security Update Process

### Dependency Updates

1. **Automated**: Dependabot creates PRs for security updates
2. **Testing**: All security updates run through comprehensive CI/CD
3. **Priority**: Security updates are prioritized over feature updates
4. **Communication**: Security-related updates are clearly documented

### Emergency Security Patches

For critical security issues:

1. **Immediate Fix**: Security patches bypass normal development workflow
2. **Fast-track Testing**: Accelerated but thorough testing process
3. **Emergency Release**: Patch versions released within 24-48 hours
4. **User Notification**: Security advisories published immediately

## 📞 Emergency Contact

For urgent security issues requiring immediate attention:

- **Project Maintainer**: GitHub Issues for urgent security matters
- **Response Time**: Best effort for this personal project

## 🙏 Recognition

Security researchers who responsibly disclose vulnerabilities will be recognized in:

- Security advisory acknowledgments
- Repository contributors list
- FINOS community security hall of fame

## 📚 Additional Resources

- [FINOS Security Policies](https://www.finos.org/security)
- [OWASP Security Guidelines](https://owasp.org/)
- [Python Security Best Practices](https://python.org/dev/security/)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)

---

Thank you for helping keep the FINOS AI Governance MCP Server secure! 🛡️
