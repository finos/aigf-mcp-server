# Cross-Framework Navigation Guide

Master the art of navigating between different governance frameworks and understanding their relationships.

## Overview

Cross-framework navigation helps you understand how different governance frameworks relate to each other, map equivalent controls, and ensure comprehensive compliance across multiple standards. This capability is essential for organizations subject to multiple regulations or those seeking best-practice coverage.

## Core Navigation Tools

### 1. Framework Correlations

**Tool**: `get_framework_correlations`

**Purpose**: Analyze the relationships and thematic overlaps between two frameworks

**Basic Usage**:
```json
{
  "framework_a": "nist_ai_rmf",
  "framework_b": "eu_ai_act"
}
```

**Detailed Analysis**:
```json
{
  "framework_a": "nist_ai_rmf",
  "framework_b": "eu_ai_act",
  "include_mappings": true
}
```

**Sample Response**:
```json
{
  "correlation_analysis": {
    "framework_a": "nist_ai_rmf",
    "framework_b": "eu_ai_act",
    "correlation_score": 0.78,
    "thematic_overlaps": [
      "Risk Management",
      "AI System Governance",
      "Documentation Requirements",
      "Human Oversight"
    ],
    "mapping_coverage": 0.85
  },
  "detailed_mappings": [
    {
      "control_a": "ai-rmf-1.1",
      "control_b": "art-17",
      "mapping_strength": "strong",
      "confidence": 0.92
    }
  ]
}
```

### 2. Related Controls

**Tool**: `get_related_controls`

**Purpose**: Find equivalent or related controls across different frameworks for a specific control

**Usage**:
```json
{
  "control_id": "ai-rmf-1.1",
  "source_framework": "nist_ai_rmf",
  "target_frameworks": ["eu_ai_act", "iso_27001"]
}
```

**Sample Response**:
```json
{
  "source_control": {
    "id": "ai-rmf-1.1",
    "framework": "nist_ai_rmf",
    "title": "Establish AI Risk Management Culture",
    "description": "Organizations shall establish and maintain a culture of AI risk management"
  },
  "related_controls": [
    {
      "control_id": "art-17",
      "framework": "eu_ai_act",
      "title": "Quality Management System",
      "relationship_strength": "strong",
      "relationship_type": "equivalent",
      "confidence_score": 0.87
    }
  ]
}
```

### 3. Compliance Gap Mapping

**Tool**: `find_compliance_gaps`

**Purpose**: Identify gaps when mapping from one framework to others

**Usage**:
```json
{
  "source_framework": "nist_ai_rmf",
  "target_frameworks": ["eu_ai_act", "gdpr"],
  "severity_threshold": "medium"
}
```

## Understanding Framework Relationships

### Relationship Types

**Equivalent** 🟢
- Controls address the same requirement
- Can be implemented with a single solution
- High confidence mapping (0.8+ correlation)

**Related** 🟡
- Controls address similar or overlapping concerns
- May require some additional work to satisfy both
- Moderate confidence mapping (0.5-0.8 correlation)

**Complementary** 🔵
- Controls work together to address broader requirements
- Each adds value to the overall control environment
- Variable confidence based on specific use case

**Conflicting** 🔴
- Controls have different or contradictory approaches
- May require careful interpretation or legal analysis
- Low confidence mapping (requires expert review)

### Mapping Strength Levels

**Strong Mapping (0.8-1.0)**
- Nearly identical requirements
- Same terminology and approach
- Can implement once to satisfy both frameworks
- High confidence in equivalence

**Moderate Mapping (0.5-0.8)**
- Similar intent, different implementation details
- May need framework-specific adaptations
- Good starting point for cross-framework compliance
- Moderate confidence in relationship

**Weak Mapping (0.2-0.5)**
- Thematically related but different focus
- Provides context but not direct equivalence
- May inform broader compliance strategy
- Low confidence in direct substitution

## Navigation Patterns

### Pattern 1: Framework Migration

**Scenario**: Moving from one framework to another (e.g., NIST to EU AI Act)

**Step-by-Step Approach**:

1. **Analyze Overall Relationship**
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

2. **Map Existing Controls**
```json
{
  "tool": "find_compliance_gaps",
  "arguments": {
    "source_framework": "nist_ai_rmf",
    "target_frameworks": ["eu_ai_act"]
  }
}
```

3. **Identify Strong Mappings**
- Focus on controls with "strong" relationship strength
- These can likely be adapted rather than rebuilt
- Document mapping rationale for audit purposes

4. **Address Unique Requirements**
- Implement controls for gaps with no equivalent
- Enhance existing controls for "moderate" mappings
- Plan timeline based on gap severity and complexity

### Pattern 2: Multi-Framework Compliance

**Scenario**: Need to comply with multiple frameworks simultaneously

**Step-by-Step Approach**:

1. **Understand All Relationships**
```json
// Analyze each pair of frameworks
{
  "tool": "get_framework_correlations",
  "arguments": {
    "framework_a": "nist_ai_rmf",
    "framework_b": "eu_ai_act"
  }
}
// Repeat for all framework pairs
```

2. **Create Master Control Mapping**
```json
// For each significant control, find related controls
{
  "tool": "get_related_controls",
  "arguments": {
    "control_id": "ai-rmf-1.1",
    "target_frameworks": ["eu_ai_act", "gdpr", "iso_27001"]
  }
}
```

3. **Optimize Control Implementation**
- Identify controls that satisfy multiple frameworks
- Prioritize high-coverage controls
- Design unified implementation approach
- Document cross-framework justification

### Pattern 3: Gap Analysis and Remediation

**Scenario**: Understanding what's missing when moving between frameworks

**Step-by-Step Approach**:

1. **Comprehensive Gap Identification**
```json
{
  "tool": "find_compliance_gaps",
  "arguments": {
    "source_framework": "current_framework",
    "target_frameworks": ["target_framework_1", "target_framework_2"],
    "severity_threshold": "low"
  }
}
```

2. **Prioritize Gaps by Impact**
- Critical gaps: Regulatory requirements, legal obligations
- High gaps: Significant risk controls, industry standards
- Medium gaps: Best practices, operational improvements
- Low gaps: Optional enhancements, future considerations

3. **Develop Remediation Strategy**
- Quick wins: Low-effort, high-impact gaps
- Strategic implementations: Complex but critical gaps
- Future roadmap: Lower priority but valuable gaps

## Framework-Specific Navigation Strategies

### NIST AI RMF ↔ EU AI Act

**Key Relationship Characteristics**:
- Strong overlap in risk management approach
- EU AI Act more prescriptive, NIST more flexible
- EU focus on legal compliance, NIST on best practices

**Navigation Strategy**:
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

**Common Mappings**:
- NIST Govern → EU AI Act Quality Management System
- NIST Map → EU AI Act Risk Assessment
- NIST Measure → EU AI Act Monitoring and Logging
- NIST Manage → EU AI Act Human Oversight

### GDPR ↔ AI Frameworks

**Key Relationship Characteristics**:
- GDPR focuses on data protection, AI frameworks on system governance
- Significant overlap in automated decision-making
- GDPR requirements often subset of broader AI governance

**Navigation Strategy**:
```json
{
  "tool": "search_frameworks",
  "arguments": {
    "query": "data protection",
    "frameworks": ["gdpr", "nist_ai_rmf", "eu_ai_act"]
  }
}
```

**Key Integration Points**:
- Data Protection Impact Assessments ↔ AI Risk Assessments
- Automated Decision-Making Rights ↔ AI Transparency Requirements
- Data Minimization ↔ AI Training Data Governance

### OWASP LLM ↔ Security Frameworks

**Key Relationship Characteristics**:
- OWASP focuses on LLM-specific vulnerabilities
- Security frameworks provide broader context
- Technical security vs. governance security

**Navigation Strategy**:
```json
{
  "tool": "get_related_controls",
  "arguments": {
    "control_id": "llm-01",
    "source_framework": "owasp_llm",
    "target_frameworks": ["iso_27001", "nist_ai_rmf"]
  }
}
```

## Advanced Navigation Techniques

### Semantic Similarity Analysis

Use search tools to find conceptually related requirements:

```json
{
  "tool": "search_frameworks",
  "arguments": {
    "query": "transparency AND explainability",
    "frameworks": ["nist_ai_rmf", "eu_ai_act", "gdpr"]
  }
}
```

**Analysis Approach**:
1. Search for key concepts across frameworks
2. Compare terminology and definitions
3. Identify common themes and differences
4. Map conceptual relationships

### Control Clustering

Group related controls across frameworks:

```json
{
  "tool": "advanced_search_frameworks",
  "arguments": {
    "query": "risk assessment",
    "include_terms": ["evaluation", "analysis", "management"],
    "frameworks": ["nist_ai_rmf", "eu_ai_act", "iso_27001"]
  }
}
```

**Clustering Strategy**:
1. Search for control themes (risk, governance, security)
2. Group results by conceptual similarity
3. Identify framework-specific approaches
4. Create unified control families

### Regulatory Hierarchy Mapping

Understand how frameworks relate in legal/regulatory context:

**Hierarchy Example**:
- **Legal Requirements** (EU AI Act, GDPR)
  - Mandatory compliance
  - Legal consequences for non-compliance
  - Specific timelines and procedures

- **Standards and Guidelines** (NIST AI RMF, ISO 27001)
  - Best practice recommendations
  - Industry adoption varies
  - Flexible implementation approaches

- **Security Frameworks** (OWASP LLM Top 10)
  - Technical implementation guidance
  - Threat-specific focus
  - Complementary to broader frameworks

## Practical Navigation Examples

### Example 1: AI System Risk Assessment

**Goal**: Implement comprehensive risk assessment covering multiple frameworks

**Navigation Approach**:

1. **Find Risk Assessment Requirements**
```json
{
  "tool": "search_frameworks",
  "arguments": {
    "query": "risk assessment",
    "frameworks": ["nist_ai_rmf", "eu_ai_act", "iso_27001"]
  }
}
```

2. **Map Risk Assessment Controls**
```json
{
  "tool": "get_related_controls",
  "arguments": {
    "control_id": "ai-rmf-2.1",
    "target_frameworks": ["eu_ai_act", "iso_27001"]
  }
}
```

3. **Unified Implementation**
- NIST AI RMF MAP function provides methodology
- EU AI Act Article 9 provides legal requirements
- ISO 27001 provides information security context
- Combine all three for comprehensive approach

### Example 2: Data Protection Integration

**Goal**: Ensure AI governance includes comprehensive data protection

**Navigation Approach**:

1. **Analyze Data Protection Overlap**
```json
{
  "tool": "get_framework_correlations",
  "arguments": {
    "framework_a": "gdpr",
    "framework_b": "nist_ai_rmf"
  }
}
```

2. **Find Data-Related AI Controls**
```json
{
  "tool": "search_frameworks",
  "arguments": {
    "query": "data",
    "frameworks": ["gdpr", "nist_ai_rmf", "eu_ai_act"],
    "limit": 20
  }
}
```

3. **Integrated Approach**
- GDPR provides legal data protection requirements
- NIST AI RMF provides AI-specific data governance
- EU AI Act provides AI system data documentation requirements
- Create unified data governance framework

### Example 3: Security Vulnerability Management

**Goal**: Integrate LLM security into broader AI risk management

**Navigation Approach**:

1. **Map Security Controls**
```json
{
  "tool": "get_related_controls",
  "arguments": {
    "control_id": "llm-01",
    "target_frameworks": ["nist_ai_rmf", "iso_27001"]
  }
}
```

2. **Find Vulnerability Context**
```json
{
  "tool": "search_frameworks",
  "arguments": {
    "query": "vulnerability",
    "frameworks": ["owasp_llm", "nist_ai_rmf", "iso_27001"]
  }
}
```

3. **Comprehensive Security Approach**
- OWASP LLM provides specific vulnerability types
- NIST AI RMF provides risk management context
- ISO 27001 provides security management framework
- Integrate all for complete security posture

## Best Practices for Cross-Framework Navigation

### 🎯 Strategic Approach

**Start with Core Framework**
- Choose primary framework based on regulatory requirements
- Use as foundation for control architecture
- Map other frameworks to core framework

**Understand Framework Intent**
- Regulatory vs. guidance frameworks
- Prescriptive vs. flexible approaches
- Industry-specific vs. general purpose

**Document Mapping Rationale**
- Record why controls are considered equivalent
- Note any gaps or additional requirements
- Maintain audit trail for compliance evidence

### 🔄 Iterative Refinement

**Regular Relationship Review**
- Framework updates may change relationships
- New guidance may affect mappings
- Industry practice evolution

**Validation and Testing**
- Test cross-framework implementations
- Validate with subject matter experts
- Confirm with legal/compliance teams

**Continuous Improvement**
- Learn from implementation experience
- Refine mappings based on results
- Share lessons learned across organization

### 📊 Measurement and Optimization

**Track Mapping Effectiveness**
- Measure effort saved through cross-framework controls
- Monitor audit success for mapped controls
- Assess stakeholder satisfaction with unified approach

**Optimize Control Portfolio**
- Identify highest-value cross-framework controls
- Prioritize controls with broad applicability
- Eliminate redundant or conflicting controls

With these navigation techniques, you can effectively manage compliance across multiple governance frameworks while optimizing effort and ensuring comprehensive coverage.