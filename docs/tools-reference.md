# 🛠️ Tools Reference

Quick reference for all 15 available tools.

## Framework Tools

### `search_frameworks`
**Purpose**: Search across all governance frameworks
**Usage**: `search_frameworks("risk management")`
**Returns**: Cross-framework search results with framework context

**Common searches**:
- `"risk management"` - Risk-related guidance across frameworks
- `"data protection"` - Data privacy requirements
- `"compliance"` - Compliance requirements and standards
- `"testing"` - Testing and validation approaches

### `list_frameworks`
**Purpose**: List all supported governance frameworks
**Usage**: `list_frameworks()`
**Returns**: Available frameworks with metadata and status

**Current frameworks**:
- **NIST AI RMF**: NIST AI Risk Management Framework (6 references)
- **EU AI Act**: European Union AI Act (5 references)
- **OWASP LLM Top 10**: OWASP LLM Security Top 10 (5 references)

### `get_framework_details`
**Purpose**: Get detailed information about a specific framework
**Usage**: `get_framework_details("nist-ai-rmf")`
**Available IDs**: nist-ai-rmf, eu-ai-act, owasp-llm-top-10

### `get_compliance_analysis`
**Purpose**: Get compliance analysis and metrics across frameworks
**Usage**: `get_compliance_analysis()`
**Returns**: Framework coverage analysis and compliance metrics

### `search_framework_references`
**Purpose**: Search within a specific framework
**Usage**: `search_framework_references("injection", "owasp-llm-top-10")`
**Returns**: Framework-specific search results

## FINOS Search Tools

### `search_mitigations`
**Purpose**: Find AI governance mitigation strategies
**Usage**: `search_mitigations("data privacy")`
**Returns**: List of matching mitigations with summaries

**Common searches**:
- `"data privacy"` - Data protection strategies
- `"security"` - Security-focused mitigations
- `"compliance"` - Regulatory compliance approaches
- `"testing"` - Testing and validation strategies

### `search_risks`
**Purpose**: Find AI risk assessments
**Usage**: `search_risks("prompt injection")`
**Returns**: List of matching risks with summaries

**Common searches**:
- `"prompt injection"` - Input manipulation attacks
- `"bias"` - AI bias and fairness issues
- `"privacy"` - Privacy-related risks
- `"adversarial"` - Adversarial attacks

## Details Tools

### `get_mitigation_details`
**Purpose**: Get full details for a specific mitigation
**Usage**: `get_mitigation_details("mi-1")`
**Available IDs**: mi-1 through mi-17

**Popular mitigations**:
- **mi-1**: Data leakage prevention
- **mi-2**: External knowledge base filtering
- **mi-3**: User/app/model firewalling
- **mi-4**: AI system observability
- **mi-5**: System acceptance testing

### `get_risk_details`
**Purpose**: Get full details for a specific risk assessment
**Usage**: `get_risk_details("ri-2")`
**Available IDs**: ri-1, ri-2, ri-3, ri-5 through ri-16, ri-19, ri-23

**Popular risks**:
- **ri-1**: Adversarial behavior against AI systems
- **ri-2**: Prompt injection attacks
- **ri-3**: Training data poisoning
- **ri-6**: Data leakage vulnerabilities

## Listing Tools

### `list_all_mitigations`
**Purpose**: Browse all available mitigations
**Usage**: `list_all_mitigations()`
**Returns**: Complete list of all 17 mitigations with metadata

### `list_all_risks`
**Purpose**: Browse all available risk assessments
**Usage**: `list_all_risks()`
**Returns**: Complete list of all 17 risks with metadata

## System Tools

### `get_service_health`
**Purpose**: Check if the server is working properly
**Usage**: `get_service_health()`
**Returns**: Health status, uptime, error counts

### `get_service_metrics`
**Purpose**: Get performance statistics
**Usage**: `get_service_metrics()`
**Returns**: Response times, request counts, success rates

### `get_cache_stats`
**Purpose**: Check cache performance
**Usage**: `get_cache_stats()`
**Returns**: Cache hit rates, memory usage, entry counts

### `reset_service_health`
**Purpose**: Reset error counters
**Usage**: `reset_service_health()`
**Returns**: Confirmation of reset

## Usage Examples

### Framework Research Workflow: Risk Management
```
1. list_frameworks()                      # See available frameworks
2. search_frameworks("risk management")   # Cross-framework search
3. get_framework_details("nist-ai-rmf")   # Get NIST details
4. get_compliance_analysis()              # Analyze coverage
```

### Framework-Specific Workflow: OWASP Security
```
1. search_framework_references("injection", "owasp-llm-top-10")
2. get_framework_details("owasp-llm-top-10")
3. search_frameworks("security testing")  # Cross-framework context
```

### FINOS Workflow: Data Protection
```
1. search_mitigations("data protection")
2. get_mitigation_details("mi-1")         # Data leakage prevention
3. search_risks("data leakage")           # Find related risks
4. get_risk_details("ri-6")               # Data leakage details
```

### FINOS Workflow: Prompt Security
```
1. search_risks("prompt injection")       # Find injection risks
2. get_risk_details("ri-2")              # Prompt injection details
3. search_mitigations("input validation") # Find protections
4. get_mitigation_details("mi-3")        # Firewalling details
```

---

**→ [Back to Setup Guide](README.md)**
