# Framework Search Guide

Master the art of finding exactly what you need across multiple governance frameworks.

## Search Tool Overview

The framework search tools provide three levels of search capability:

1. **Multi-Framework Search** (`search_frameworks`) - Search across all frameworks simultaneously
2. **Framework-Specific Search** (`search_framework_references`) - Deep search within a single framework
3. **Advanced Search** (`advanced_search_frameworks`) - Complex queries with advanced filtering

## Multi-Framework Search

### Basic Multi-Framework Search

**Tool**: `search_frameworks`

**Best for**: Getting a broad overview of how different frameworks address a topic

**Basic Usage**:
```json
{
  "query": "data protection",
  "limit": 20
}
```

**Advanced Usage**:
```json
{
  "query": "risk assessment",
  "frameworks": ["nist_ai_rmf", "eu_ai_act", "owasp_llm"],
  "severity": "high",
  "compliance_status": "non_compliant",
  "limit": 15
}
```

### Understanding Search Results

**Sample Result**:
```json
{
  "query": "data protection",
  "total_results": 23,
  "frameworks_searched": ["nist_ai_rmf", "eu_ai_act", "gdpr"],
  "results": [
    {
      "framework": "gdpr",
      "reference_id": "art-25",
      "title": "Data Protection by Design and by Default",
      "content": "The controller shall implement appropriate technical and organisational measures...",
      "relevance_score": 0.95,
      "severity": "high",
      "compliance_status": "compliant"
    }
  ]
}
```

**Key Elements**:
- **relevance_score**: How well the content matches your query
  - 0.9-1.0: Highly relevant, exactly what you're looking for
  - 0.7-0.9: Very relevant, worth detailed review
  - 0.5-0.7: Moderately relevant, may be useful
  - 0.3-0.5: Somewhat related, context-dependent value
- **severity**: Importance level in the framework
- **compliance_status**: Current assessment status

### Search Query Strategies

#### 1. Conceptual Searches
Search for broad concepts that might be expressed differently across frameworks:

**Examples**:
- "transparency" (finds disclosure, explainability, interpretability)
- "accountability" (finds responsibility, liability, oversight)
- "bias" (finds fairness, discrimination, equity)
- "security" (finds protection, safeguards, controls)

#### 2. Specific Term Searches
Search for exact technical terms:

**Examples**:
- "prompt injection" (specific LLM vulnerability)
- "data subject rights" (specific GDPR concept)
- "algorithmic impact assessment" (specific AI governance practice)
- "model governance" (specific AI management practice)

#### 3. Process-Based Searches
Search for governance processes and activities:

**Examples**:
- "risk assessment" (evaluation processes)
- "monitoring and review" (ongoing oversight)
- "incident response" (handling problems)
- "training and awareness" (human factors)

#### 4. Multi-Term Searches
Combine terms for more precise results:

**Examples**:
- "AI system testing" (specific to AI, not general testing)
- "data protection impact assessment" (specific GDPR process)
- "third party risk management" (supply chain governance)
- "automated decision making" (algorithmic decision processes)

## Framework-Specific Search

### Deep Dive Search

**Tool**: `search_framework_references`

**Best for**: Finding specific requirements within a particular framework you're focusing on

**Usage**:
```json
{
  "framework_id": "eu_ai_act",
  "query": "high-risk AI systems",
  "category": "risk_classification",
  "limit": 10
}
```

**When to use framework-specific search**:
- You're implementing a specific framework
- You need detailed requirements from one standard
- You want to understand a framework's approach to a topic
- You're creating framework-specific documentation

### Category Filtering

Many frameworks organize content into categories. Use these for focused searches:

**NIST AI RMF Categories**:
- "governance" - Organizational aspects
- "map" - Risk identification and analysis
- "measure" - Risk measurement and assessment
- "manage" - Risk response and mitigation

**EU AI Act Categories**:
- "risk_classification" - Risk level determination
- "prohibited_practices" - Banned AI uses
- "high_risk_requirements" - Requirements for high-risk systems
- "transparency_obligations" - Disclosure requirements

**GDPR Categories**:
- "lawful_basis" - Legal grounds for processing
- "data_subject_rights" - Individual rights
- "controller_obligations" - Data controller duties
- "processor_requirements" - Data processor duties

## Advanced Search

### Complex Query Building

**Tool**: `advanced_search_frameworks`

**Best for**: Complex research requiring multiple criteria and exclusions

**Advanced Features**:
- **Include/Exclude Terms**: Must have certain terms, must not have others
- **Category Filtering**: Limit to specific framework sections
- **Date Ranges**: Find recently added or updated content
- **Combination Logic**: Complex Boolean-style queries

**Example Usage**:
```json
{
  "query": "artificial intelligence",
  "include_terms": ["risk", "assessment"],
  "exclude_terms": ["training", "development"],
  "categories": ["governance", "risk_management"],
  "date_range": {
    "start": "2023-01-01",
    "end": "2024-12-31"
  }
}
```

### Search Patterns for Common Scenarios

#### Compliance Gap Analysis
```json
{
  "query": "monitoring",
  "frameworks": ["nist_ai_rmf", "eu_ai_act"],
  "severity": ["high", "critical"],
  "compliance_status": "non_compliant"
}
```
*Find high-priority monitoring requirements you're not meeting*

#### Risk Management Research
```json
{
  "query": "risk",
  "include_terms": ["assessment", "mitigation", "management"],
  "exclude_terms": ["financial", "credit"],
  "frameworks": ["nist_ai_rmf", "iso_27001"]
}
```
*Focus on operational risk, not financial risk*

#### Privacy Compliance Analysis
```json
{
  "query": "data protection",
  "frameworks": ["gdpr", "ccpa"],
  "category": "data_subject_rights"
}
```
*Compare privacy rights across regulations*

#### Security Vulnerability Research
```json
{
  "query": "vulnerability",
  "frameworks": ["owasp_llm"],
  "severity": ["critical", "high"]
}
```
*Find critical security issues for LLMs*

## Search Best Practices

### 🎯 Query Optimization

#### Start Broad, Then Narrow
1. Begin with general terms: "privacy", "security", "risk"
2. Review results to understand framework terminology
3. Refine with specific terms found in initial results
4. Use framework-specific searches for detailed requirements

#### Use Framework Terminology
Different frameworks use different terms for similar concepts:

| Concept | NIST AI RMF | EU AI Act | GDPR |
|---------|-------------|-----------|------|
| Data Protection | "Privacy" | "Data Protection" | "Data Protection" |
| Algorithmic Bias | "Fairness" | "Bias Monitoring" | "Automated Decision Making" |
| System Testing | "Verification" | "Conformity Assessment" | "Data Protection Impact Assessment" |
| Transparency | "Explainability" | "Transparency Obligations" | "Information to Data Subjects" |

#### Handling Synonyms and Variations
Try multiple search terms for the same concept:
- "AI system" OR "artificial intelligence system" OR "automated system"
- "data subject" OR "individual" OR "person" OR "user"
- "risk assessment" OR "risk evaluation" OR "risk analysis"
- "monitoring" OR "oversight" OR "supervision" OR "audit"

### 📊 Interpreting Results

#### Relevance Score Guidelines
- **0.9-1.0**: Direct match - exactly what you searched for
- **0.7-0.9**: High relevance - strongly related to your topic
- **0.5-0.7**: Moderate relevance - useful context or related concepts
- **0.3-0.5**: Low relevance - tangentially related, may provide background
- **Below 0.3**: Minimal relevance - likely not useful for your purpose

#### Severity Level Interpretation
- **Critical**: Legal requirements, regulatory mandates, core governance
- **High**: Important best practices, significant risk controls
- **Medium**: Standard operating procedures, recommended practices
- **Low**: Guidelines, suggestions, contextual information

#### Framework Context Matters
The same relevance score means different things in different frameworks:
- GDPR: Legal requirements (high scores = legal obligations)
- NIST AI RMF: Best practices (high scores = recommended approaches)
- OWASP LLM: Security vulnerabilities (high scores = security risks)

### 🔄 Iterative Search Strategy

#### Phase 1: Discovery
- Use broad terms across all frameworks
- Review top 20 results for terminology patterns
- Note which frameworks have most relevant content
- Identify specific terms and concepts for deeper search

#### Phase 2: Deep Dive
- Use framework-specific search on most relevant frameworks
- Search for specific terms discovered in Phase 1
- Use category filters to focus on relevant sections
- Build understanding of framework-specific approaches

#### Phase 3: Comprehensive Coverage
- Use advanced search with include/exclude terms
- Cross-reference findings across frameworks
- Look for gaps in coverage using compliance analysis
- Document findings and create action plans

### 🚀 Performance Tips

#### Optimize Search Speed
- Use appropriate limits (10-20 for exploration, 5-10 for focused searches)
- Search specific frameworks when you know where to look
- Use caching - repeated searches return instantly
- Check service health if searches are slow

#### Manage Large Result Sets
- Use severity filtering to prioritize important content
- Filter by compliance status to focus on gaps
- Use framework filtering to reduce noise
- Export large result sets for offline analysis

## Common Search Scenarios

### Scenario 1: New Framework Implementation
**Goal**: Understand all requirements for implementing EU AI Act compliance

**Search Strategy**:
1. `get_framework_details {"framework_id": "eu_ai_act"}`
2. `search_framework_references {"framework_id": "eu_ai_act", "query": "requirements", "limit": 50}`
3. `search_framework_references {"framework_id": "eu_ai_act", "query": "obligations", "category": "high_risk_requirements"}`

### Scenario 2: Cross-Framework Compliance
**Goal**: Ensure AI risk management covers both NIST and EU requirements

**Search Strategy**:
1. `search_frameworks {"query": "risk management", "frameworks": ["nist_ai_rmf", "eu_ai_act"]}`
2. `get_framework_correlations {"framework_a": "nist_ai_rmf", "framework_b": "eu_ai_act"}`
3. `find_compliance_gaps {"source_framework": "nist_ai_rmf", "target_frameworks": ["eu_ai_act"]}`

### Scenario 3: Security Vulnerability Assessment
**Goal**: Identify all AI security vulnerabilities and corresponding controls

**Search Strategy**:
1. `search_frameworks {"query": "security", "frameworks": ["owasp_llm", "nist_ai_rmf", "iso_27001"]}`
2. `search_framework_references {"framework_id": "owasp_llm", "query": "vulnerability"}`
3. `get_related_controls {"control_id": "llm-01", "target_frameworks": ["nist_ai_rmf", "iso_27001"]}`

### Scenario 4: Privacy Impact Assessment
**Goal**: Understand privacy requirements across all applicable frameworks

**Search Strategy**:
1. `search_frameworks {"query": "privacy", "frameworks": ["gdpr", "ccpa", "nist_ai_rmf"]}`
2. `search_framework_references {"framework_id": "gdpr", "query": "impact assessment"}`
3. `advanced_search_frameworks {"query": "data protection", "include_terms": ["assessment", "evaluation"], "frameworks": ["gdpr", "ccpa"]}`

## Troubleshooting Search Issues

### No Results Found
**Possible causes**:
- Overly specific query terms
- Typos in search terms
- Framework-specific terminology mismatch
- Too restrictive filters

**Solutions**:
- Try broader, more general terms
- Check spelling and try variations
- Remove filters and search all frameworks
- Use synonyms or related terms

### Too Many Results
**Possible causes**:
- Very broad search terms
- No filtering applied
- Searching all frameworks unnecessarily

**Solutions**:
- Add specific terms to narrow focus
- Use severity or compliance status filters
- Limit to relevant frameworks only
- Use category filtering

### Irrelevant Results
**Possible causes**:
- Ambiguous search terms
- Cross-domain terminology confusion
- Insufficient context in query

**Solutions**:
- Use more specific, technical terms
- Add context terms (e.g., "AI risk" not just "risk")
- Use exclude terms to remove irrelevant content
- Try framework-specific searches

### Slow Search Performance
**Possible causes**:
- Large result sets being processed
- Multiple frameworks being searched
- External framework data loading

**Solutions**:
- Reduce search limits
- Search fewer frameworks simultaneously
- Check service health status
- Use cached results when possible

Search effectively with these strategies and you'll quickly become proficient at finding exactly the governance content you need across any combination of frameworks.