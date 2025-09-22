# Compliance Analysis Guide

Master compliance assessment and gap analysis across multiple governance frameworks.

## Overview

Compliance analysis helps you understand how well your organization meets governance requirements across different frameworks. This guide covers tools and techniques for assessing compliance status, identifying gaps, and tracking progress.

## Core Compliance Tools

### 1. Overall Compliance Assessment

**Tool**: `get_compliance_analysis`

**Purpose**: Get a comprehensive view of compliance across all or selected frameworks

**Basic Usage**:
```json
{
  "include_gaps": true
}
```

**Targeted Analysis**:
```json
{
  "frameworks": ["nist_ai_rmf", "eu_ai_act", "gdpr"],
  "include_gaps": true
}
```

**Sample Response**:
```json
{
  "analysis_summary": {
    "frameworks_analyzed": 3,
    "total_requirements": 125,
    "overall_compliance_rate": 78.5,
    "critical_gaps": 5,
    "analysis_date": "2024-01-15T14:30:00Z"
  },
  "framework_compliance": [
    {
      "framework": "nist_ai_rmf",
      "compliance_rate": 85.7,
      "compliant_controls": 24,
      "non_compliant_controls": 4,
      "partially_compliant_controls": 2,
      "total_controls": 30,
      "status": "good"
    }
  ],
  "cross_framework_gaps": [
    {
      "gap_type": "coverage",
      "description": "GDPR data protection requirements not fully covered by NIST framework",
      "severity": "high"
    }
  ]
}
```

### 2. Gap Analysis

**Tool**: `find_compliance_gaps`

**Purpose**: Identify specific gaps when mapping from one framework to others

**Usage**:
```json
{
  "source_framework": "nist_ai_rmf",
  "target_frameworks": ["eu_ai_act", "gdpr"],
  "severity_threshold": "medium"
}
```

**Sample Response**:
```json
{
  "gap_analysis": {
    "source_framework": "nist_ai_rmf",
    "target_frameworks": ["eu_ai_act", "gdpr"],
    "total_gaps": 12,
    "critical_gaps": 3
  },
  "gaps": [
    {
      "gap_type": "missing_control",
      "severity": "high",
      "description": "EU AI Act requires specific conformity assessment procedures not addressed in NIST framework",
      "affected_frameworks": ["eu_ai_act"],
      "recommendations": [
        "Implement conformity assessment procedures",
        "Document CE marking process"
      ]
    }
  ]
}
```

## Compliance Workflow Patterns

### Pattern 1: Initial Compliance Assessment

**Scenario**: New to governance frameworks, need baseline assessment

**Step-by-Step Workflow**:

1. **Discover Available Frameworks**
```json
{
  "tool": "list_frameworks",
  "arguments": {"include_stats": true}
}
```

2. **Get Overall Compliance Status**
```json
{
  "tool": "get_compliance_analysis",
  "arguments": {"include_gaps": true}
}
```

3. **Analyze Critical Gaps**
- Review `critical_gaps` count in analysis summary
- Focus on gaps with severity "critical" or "high"
- Prioritize based on regulatory requirements

4. **Create Action Plan**
- Export findings for stakeholder review
- Assign responsibility for each gap
- Set timelines based on severity and complexity

### Pattern 2: Framework-Specific Deep Dive

**Scenario**: Implementing a specific framework (e.g., EU AI Act compliance)

**Step-by-Step Workflow**:

1. **Get Framework Overview**
```json
{
  "tool": "get_framework_details",
  "arguments": {
    "framework_id": "eu_ai_act",
    "include_references": true
  }
}
```

2. **Assess Current Compliance**
```json
{
  "tool": "get_compliance_analysis",
  "arguments": {
    "frameworks": ["eu_ai_act"],
    "include_gaps": true
  }
}
```

3. **Identify Specific Requirements**
```json
{
  "tool": "search_framework_references",
  "arguments": {
    "framework_id": "eu_ai_act",
    "query": "requirements",
    "category": "high_risk_requirements"
  }
}
```

4. **Map to Existing Controls**
```json
{
  "tool": "find_compliance_gaps",
  "arguments": {
    "source_framework": "nist_ai_rmf",
    "target_frameworks": ["eu_ai_act"]
  }
}
```

### Pattern 3: Cross-Framework Compliance

**Scenario**: Need to comply with multiple frameworks simultaneously

**Step-by-Step Workflow**:

1. **Analyze Framework Relationships**
```json
{
  "tool": "get_framework_correlations",
  "arguments": {
    "framework_a": "nist_ai_rmf",
    "framework_b": "eu_ai_act",
    "include_mappings": true
  }
}
```

2. **Comprehensive Gap Analysis**
```json
{
  "tool": "find_compliance_gaps",
  "arguments": {
    "source_framework": "nist_ai_rmf",
    "target_frameworks": ["eu_ai_act", "gdpr", "owasp_llm"]
  }
}
```

3. **Identify Overlapping Requirements**
- Look for controls that satisfy multiple frameworks
- Focus on gaps unique to each framework
- Prioritize controls with highest cross-framework value

4. **Develop Integrated Approach**
- Create unified control framework
- Map single controls to multiple requirements
- Optimize effort across frameworks

## Understanding Compliance Metrics

### Compliance Rates

**Interpretation Guide**:
- **90-100%**: Excellent compliance, minor gaps only
- **80-89%**: Good compliance, some gaps to address
- **70-79%**: Moderate compliance, significant work needed
- **60-69%**: Poor compliance, major gaps to address
- **Below 60%**: Critical compliance issues, immediate action required

### Compliance Status Values

**Status Definitions**:
- **Compliant**: Requirement fully implemented and verified
- **Partially Compliant**: Some aspects implemented, others missing
- **Non-Compliant**: Requirement not implemented
- **Not Assessed**: Status unknown or not yet evaluated

### Gap Types

**Understanding Gap Categories**:
- **missing_control**: Required control not implemented
- **insufficient_coverage**: Control exists but doesn't fully meet requirement
- **conflicting_requirement**: Requirements conflict between frameworks
- **coverage**: Framework doesn't address certain areas
- **implementation**: Technical implementation gaps

### Severity Levels in Compliance Context

**Severity Interpretation**:
- **Critical**: Legal/regulatory requirements, compliance mandatory
- **High**: Important governance controls, significant risk if missing
- **Medium**: Best practice requirements, moderate risk if missing
- **Low**: Recommended practices, minimal risk if missing

## Advanced Compliance Analysis

### Multi-Dimensional Analysis

**Analyze by Multiple Criteria**:

1. **By Framework Type**
```json
{
  "tool": "get_compliance_analysis",
  "arguments": {
    "frameworks": ["nist_ai_rmf", "eu_ai_act"],  // Regulatory frameworks
    "include_gaps": true
  }
}
```

2. **By Risk Level**
```json
{
  "tool": "search_frameworks",
  "arguments": {
    "query": "high-risk",
    "frameworks": ["eu_ai_act", "nist_ai_rmf"],
    "severity": ["critical", "high"],
    "compliance_status": "non_compliant"
  }
}
```

3. **By Implementation Complexity**
- Use export tools to analyze requirements by category
- Group by technical vs. organizational requirements
- Prioritize by resource requirements and timeline

### Compliance Trending

**Track Compliance Over Time**:

1. **Baseline Assessment** (Month 1)
- Complete initial compliance analysis
- Document all gaps and current status
- Export results for historical comparison

2. **Progress Reviews** (Monthly)
- Re-run compliance analysis
- Compare to baseline metrics
- Track gap closure and new requirements

3. **Trend Analysis** (Quarterly)
- Analyze compliance rate changes
- Identify patterns in gap types
- Adjust implementation strategies

### Risk-Based Compliance Prioritization

**Prioritization Framework**:

1. **Legal/Regulatory Requirements** (Priority 1)
- All "critical" severity items
- Regulatory compliance requirements
- Items with legal consequences if missing

2. **High-Risk Controls** (Priority 2)
- "High" severity items
- Controls protecting critical assets
- Items with significant business impact

3. **Best Practices** (Priority 3)
- "Medium" and "low" severity items
- Industry standard practices
- Continuous improvement items

## Compliance Reporting

### Executive Summary Reports

**Key Metrics for Leadership**:
- Overall compliance percentage
- Number of critical gaps
- Regulatory compliance status
- Implementation timeline and resource needs

**Sample Executive Summary**:
```
AI Governance Compliance Status

Overall Compliance: 78.5%
Critical Gaps: 5 items requiring immediate attention
Regulatory Status:
  - EU AI Act: 72% compliant (8 gaps)
  - NIST AI RMF: 85% compliant (4 gaps)
  - GDPR: 91% compliant (2 gaps)

Priority Actions:
1. Implement conformity assessment procedures (EU AI Act)
2. Enhance AI system documentation (NIST AI RMF)
3. Complete data protection impact assessments (GDPR)

Resource Requirements: 6 months, 3 FTE
Next Review: 30 days
```

### Technical Gap Reports

**Detailed Analysis for Implementation Teams**:

```json
{
  "tool": "export_framework_data",
  "arguments": {
    "framework_id": "eu_ai_act",
    "format": "csv",
    "filters": {
      "compliance_status": ["non_compliant", "partially_compliant"],
      "severity": ["critical", "high"]
    }
  }
}
```

### Cross-Framework Mapping Reports

**For Understanding Relationships**:

```json
{
  "tool": "bulk_export_frameworks",
  "arguments": {
    "exports": [
      {
        "framework_id": "nist_ai_rmf",
        "format": "json",
        "filters": {"compliance_status": ["non_compliant"]}
      },
      {
        "framework_id": "eu_ai_act",
        "format": "json",
        "filters": {"compliance_status": ["non_compliant"]}
      }
    ]
  }
}
```

## Common Compliance Scenarios

### Scenario 1: Pre-Audit Assessment

**Goal**: Prepare for external compliance audit

**Approach**:
1. Complete comprehensive compliance analysis
2. Focus on regulatory requirements (critical/high severity)
3. Document evidence for compliant controls
4. Create remediation plan for gaps
5. Export detailed reports for auditor review

**Key Tools**:
- `get_compliance_analysis` for overall status
- `search_frameworks` with compliance filters
- `export_framework_data` for audit documentation

### Scenario 2: New Product Launch

**Goal**: Ensure new AI product meets all applicable requirements

**Approach**:
1. Identify applicable frameworks based on product characteristics
2. Analyze requirements specific to product use case
3. Map product features to compliance requirements
4. Identify gaps in current product design
5. Integrate compliance into development roadmap

**Key Tools**:
- `search_frameworks` for product-specific requirements
- `get_related_controls` for comprehensive coverage
- `find_compliance_gaps` for missing requirements

### Scenario 3: Regulatory Change Management

**Goal**: Adapt to new or updated regulations

**Approach**:
1. Compare current compliance to updated requirements
2. Identify new requirements not previously covered
3. Assess impact on existing controls and processes
4. Prioritize implementation based on effective dates
5. Update compliance monitoring and reporting

**Key Tools**:
- `get_framework_details` for regulation updates
- `get_framework_correlations` for impact analysis
- `find_compliance_gaps` for new requirements

### Scenario 4: Vendor Due Diligence

**Goal**: Assess vendor compliance for AI services

**Approach**:
1. Define applicable frameworks for vendor services
2. Create vendor assessment questionnaire
3. Map vendor capabilities to requirements
4. Identify gaps in vendor compliance
5. Negotiate compliance requirements in contracts

**Key Tools**:
- `search_frameworks` for vendor-relevant requirements
- `export_framework_data` for assessment templates
- `get_compliance_analysis` for gap identification

## Troubleshooting Compliance Analysis

### Issue: Low Compliance Rates Across All Frameworks

**Possible Causes**:
- Initial implementation, many controls not yet in place
- Incorrect compliance status assessment
- Overly strict compliance criteria

**Solutions**:
- Focus on critical and high-severity items first
- Review compliance status definitions
- Implement phased compliance approach
- Consider partial compliance as progress toward full compliance

### Issue: Conflicting Requirements Between Frameworks

**Possible Causes**:
- Different regulatory approaches to same issues
- Framework interpretation differences
- Translation or terminology issues

**Solutions**:
- Use `get_framework_correlations` to understand relationships
- Consult legal/compliance experts for interpretation
- Implement controls that satisfy the strictest requirements
- Document rationale for compliance approach

### Issue: Gaps in Framework Coverage

**Possible Causes**:
- Framework doesn't address all organizational needs
- Industry-specific requirements not covered
- Emerging risks not yet in frameworks

**Solutions**:
- Supplement with industry-specific standards
- Add custom organizational requirements
- Monitor framework updates for new coverage
- Use multiple frameworks for comprehensive coverage

## Best Practices for Ongoing Compliance

### 🔄 Regular Assessment Cycle

**Monthly Reviews**:
- Quick compliance status check
- Review newly identified gaps
- Update implementation progress
- Escalate critical issues

**Quarterly Deep Dives**:
- Comprehensive compliance analysis
- Framework correlation review
- Gap trend analysis
- Strategy adjustment

**Annual Assessments**:
- Complete framework review
- External validation/audit
- Strategy and tool evaluation
- Framework portfolio optimization

### 📊 Metrics and KPIs

**Track These Key Indicators**:
- Overall compliance percentage trend
- Time to close critical gaps
- Number of new gaps identified
- Framework coverage breadth
- Cost per compliance control

### 🎯 Continuous Improvement

**Improvement Strategies**:
- Automate compliance monitoring where possible
- Integrate compliance into development processes
- Regular training on framework requirements
- Benchmark against industry peers
- Participate in framework development processes

With these tools and techniques, you can maintain strong compliance posture across multiple governance frameworks while efficiently managing resources and minimizing compliance burden.
