# Independent AI Governance MCP Server - Security Policy

## 🛡️ Security Overview

This independent AI Governance MCP Server project takes security seriously and follows advanced security practices to protect users and maintain the integrity of AI governance content access.

## 🔒 Security Features

### Built-in Security Controls

- **Input Validation**: All user inputs validated with Pydantic schemas and field validators
- **HTTP Security**: Secure HTTP client with timeout controls and SSRF protection
- **Configuration Security**: Environment variable validation and path traversal protection
- **GitHub Token Security**: Comprehensive token format validation and secure storage
- **Rate Limiting**: Built-in GitHub API rate limiting with exponential backoff
- **Dependency Security**: Regular vulnerability scanning with Safety and pip-audit

### Security Scanning Infrastructure

- ✅ **Ruff Security Linting**: Fast Python security issue detection and code quality checks
- ✅ **MyPy Static Type Checking**: Type safety validation to prevent runtime errors
- ✅ **Safety Dependency Scanning**: Known vulnerability detection in Python packages
- ✅ **Pytest Security Testing**: Comprehensive test coverage including security edge cases
- ✅ **Configuration Validation**: Startup validation of all security-related settings

## 🚨 Reporting Security Vulnerabilities

**IMPORTANT**: Do not report security vulnerabilities through public GitHub issues.

### For Security Vulnerabilities

1. **GitHub Security Advisory**: Create a [Security Advisory](https://github.com/<OWNER>/<REPO>/security/advisories) for responsible disclosure
3. **Include**:
   - Detailed description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact assessment
   - Suggested mitigation (if available)
4. **Response**: Best effort acknowledgment
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
# ✅ GOOD: Pydantic validation (actual implementation)
from pydantic import BaseModel, Field, field_validator
from finos_mcp.security.validators import ValidationError, validate_search_request

class SearchQueryValidator(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    exact_match: bool = Field(default=False)

    @field_validator("query")
    @classmethod
    def validate_query_schema(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Search query cannot be empty")

        query = v.strip()
        if len(query) > 500:
            raise ValueError("Search query exceeds 500 character limit")

        return query

# Usage in application
def handle_search(query: str, exact_match: bool = False):
    try:
        validated = validate_search_request(query, exact_match)
        return validated  # {"query": sanitized_query, "exact_match": bool}
    except ValidationError as e:
        logger.warning(f"Search validation failed: {e.message}")
        raise
```

#### 3. Secure HTTP Practices
```python
# ✅ GOOD: Secure HTTP client usage (actual implementation)
from finos_mcp.config import get_settings

settings = get_settings()
async with httpx.AsyncClient(
    timeout=httpx.Timeout(settings.http_timeout),
    follow_redirects=False,  # Prevent redirect attacks
    verify=True,            # Verify SSL certificates
    headers={'User-Agent': f'finos-mcp/{settings.server_version}'}
) as client:
    response = await client.get(url)
    response.raise_for_status()
```

#### 4. Error Handling
```python
# ✅ GOOD: Secure error handling (actual implementation)
import logging
from mcp.server.exceptions import McpError

logger = logging.getLogger(__name__)

try:
    result = await process_user_input(data)
    return result
except ValueError as e:
    # Log error without exposing internals
    logger.warning("Invalid input received", extra={"error_type": "validation"})
    raise McpError("INVALID_REQUEST", "Invalid input provided")
except Exception as e:
    # Never expose internal error details to users
    logger.error("Internal processing error", exc_info=True)
    raise McpError("INTERNAL_ERROR", "Internal server error occurred")
```

### Security Validation Tools

All code changes are validated with:

- **Ruff**: Fast Python linting with security rules enabled
- **MyPy**: Static type checking to prevent runtime security issues
- **Safety**: Dependency vulnerability scanning for known CVEs
- **Pytest**: Comprehensive security testing including edge cases

## 🔍 Security Scanning Results

### Current Security Status

As of the latest validation:

- ✅ **Ruff**: No security linting issues detected
- ✅ **MyPy**: No type safety violations
- ✅ **Safety**: No known vulnerabilities in dependencies
- ✅ **Pytest**: 85%+ test coverage including security edge cases
- ✅ **Configuration**: All security settings validated at startup

### Continuous Validation

Security validation runs:

- **Development**: Ruff and MyPy on every code change
- **Testing**: Safety scans with dependency updates
- **CI/CD**: Full security test suite on pull requests
- **Runtime**: Configuration validation on startup

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

## 🙏 Recognition

Security researchers who responsibly disclose vulnerabilities will be recognized in:

- Security advisory acknowledgments
- Repository contributors list
- Project documentation and release notes

## 📚 Additional Resources

- [FINOS Security Policies](https://www.finos.org/security)
- [OWASP Security Guidelines](https://owasp.org/)
- [Python Security Best Practices](https://python.org/dev/security/)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)

---

Thank you for helping keep this AI Governance MCP Server secure! 🛡️
