# Framework System Architecture

Comprehensive documentation of the governance framework system architecture, design patterns, and integration capabilities.

## System Overview

The FINOS MCP Server implements a multi-layer architecture designed for scalability, security, and extensibility in governance framework operations.

```mermaid
graph TB
    %% External Connections
    Claude[Claude Desktop/VS Code/Cursor] --> MCP[MCP Protocol Layer]

    %% Core System Layers
    MCP --> Security[Security & Validation Layer]
    Security --> Router[Tool Router & Registry]

    %% Tool Categories
    Router --> FrameworkTools[Framework Access Tools<br/>5 tools]
    Router --> RiskMitigationTools[Risk & Mitigation Tools<br/>4 tools]
    Router --> SystemTools[System Monitoring Tools<br/>2 tools]

    %% Framework System
    FrameworkTools --> QueryEngine[Framework Query Engine]
    RiskMitigationTools --> QueryEngine

    %% Core Framework Components
    QueryEngine --> DataLoader[Dynamic Data Loader]
    QueryEngine --> CrossMapper[Cross-Framework Mapper]
    QueryEngine --> ContentService[Content Service]

    %% Data Sources & Storage
    DataLoader --> DynamicLoaders[Dynamic Loaders<br/>GDPR • CCPA • ISO42001 • FFIEC]
    DataLoader --> StaticData[Static Framework Data<br/>NIST AI RMF • EU AI Act • OWASP LLM]
    ContentService --> FINOSRepo[FINOS Repository<br/>Mitigations & Risks]

    %% Cross-Reference System
    CrossMapper --> MappingTables[Cross-Reference Tables<br/>Framework Correlations]
    CrossMapper --> CorrelationEngine[Correlation Analysis<br/>Strength Indicators]

    %% Caching & Performance
    DataLoader --> Cache[Intelligent Cache<br/>TTL • Circuit Breaker]
    QueryEngine --> SearchIndex[Search Indices<br/>Text • Category • Compliance]

    %% Export & Analysis
    QueryEngine --> ExportEngine[Export Engine<br/>JSON • CSV • Markdown]
    QueryEngine --> Analytics[Compliance Analytics<br/>Gap Analysis • Coverage]

    %% Styling
    classDef tool fill:#e1f5fe
    classDef framework fill:#f3e5f5
    classDef data fill:#e8f5e8
    classDef cache fill:#fff3e0

    class FrameworkTools,RiskMitigationTools,SystemTools tool
    class QueryEngine,CrossMapper,DataLoader,ContentService framework
    class DynamicLoaders,StaticData,FINOSRepo,MappingTables data
    class Cache,SearchIndex,ExportEngine,Analytics cache
```

## Core Components

### 1. Framework Data Loader (`FrameworkDataLoader`)

**Purpose**: Dynamic loading and management of governance framework data.

**Key Features**:
- Dynamic content fetching from official sources
- Intelligent caching with TTL management
- Circuit breaker protection for external dependencies
- Support for both static and dynamic frameworks

**Supported Framework Types**:
- **Active Frameworks**: Live data from official sources (NIST, EU, OWASP, GDPR)
- **Modeled Frameworks**: Internal representations (CCPA, ISO 27001, SOC 2)

**Implementation Pattern**:
```python
class FrameworkDataLoader:
    async def load_all_frameworks(self) -> List[Framework]
    async def load_framework(self, framework_id: str) -> Framework
    async def refresh_framework(self, framework_id: str) -> bool
```

### 2. Framework Query Engine (`FrameworkQueryEngine`)

**Purpose**: Unified query interface across all governance frameworks.

**Capabilities**:
- Multi-framework search with relevance scoring
- Semantic similarity matching
- Advanced filtering (severity, compliance status, categories)
- Result ranking and pagination

**Query Processing Pipeline**:
```mermaid
graph LR
    A[User Query] --> B[Query Normalization]
    B --> C[Framework Selection]
    C --> D[Content Search]
    D --> E[Relevance Scoring]
    E --> F[Result Ranking]
    F --> G[Response Generation]

    %% Styling
    classDef process fill:#e3f2fd
    classDef result fill:#e8f5e8

    class B,C,D,E,F process
    class A,G result
```

**Performance Optimizations**:
- In-memory indexing for fast searches
- Query result caching
- Lazy loading of framework content
- Parallel framework searches

### 3. Cross-Framework Mapper (`CrossFrameworkMapper`)

**Purpose**: Intelligent mapping between different governance frameworks.

**Framework Relationship Matrix**:
```mermaid
graph TD
    subgraph "AI/ML Frameworks"
        NIST[NIST AI RMF<br/>6 refs, 4 sections]
        EU[EU AI Act<br/>5 refs, 4 sections]
        OWASP[OWASP LLM Top 10<br/>5 refs, 4 sections]
    end

    subgraph "Privacy & Data"
        GDPR[GDPR<br/>9 sections, 18 refs]
        CCPA[CCPA<br/>Dynamic Loader]
    end

    subgraph "General Compliance"
        ISO[ISO 27001<br/>Modeled]
        SOC[SOC 2<br/>Modeled]
    end

    %% Strong Mappings (0.8-1.0)
    NIST -.->|0.85| EU
    GDPR -.->|0.90| CCPA

    %% Moderate Mappings (0.5-0.8)
    NIST -.->|0.75| OWASP
    EU -.->|0.65| OWASP
    GDPR -.->|0.70| EU

    %% Weak Mappings (0.2-0.5)
    ISO -.->|0.45| NIST
    SOC -.->|0.40| ISO

    %% Styling
    classDef ai fill:#e3f2fd
    classDef privacy fill:#f3e5f5
    classDef general fill:#e8f5e8

    class NIST,EU,OWASP ai
    class GDPR,CCPA privacy
    class ISO,SOC general
```

**Mapping Types & Strength Levels**:
- **Equivalent** (0.8-1.0): Direct 1:1 control mapping
- **Related** (0.5-0.8): Thematically similar controls
- **Complementary** (0.2-0.5): Controls that work together

### 4. Content Service Integration

**Purpose**: Unified interface for accessing diverse content sources.

**Data Flow Architecture**:
```mermaid
graph TB
    subgraph "External Sources"
        GitHub[GitHub Repos<br/>FINOS • Standards Bodies]
        Official[Official Sources<br/>NIST • EU • OWASP]
        APIs[Public APIs<br/>Standards Data]
    end

    subgraph "Dynamic Loading System"
        Loaders[Framework Loaders<br/>GDPR • CCPA • ISO42001 • FFIEC]
        HTTP[HTTP Client<br/>Circuit Breaker • Retry Logic]
        Validation[Content Validation<br/>Schema • Integrity Checks]
    end

    subgraph "Caching Layer"
        Memory[Memory Cache<br/>LRU • TTL]
        Disk[Disk Cache<br/>Persistent Storage]
        Invalidation[Cache Invalidation<br/>Smart Refresh]
    end

    subgraph "Processing Engine"
        Parser[Content Parser<br/>YAML • JSON • Markdown]
        Indexer[Search Indexer<br/>Full-text • Categories]
        Analytics[Content Analytics<br/>Statistics • Health]
    end

    %% Data Flow
    GitHub --> Loaders
    Official --> Loaders
    APIs --> Loaders

    Loaders --> HTTP
    HTTP --> Validation
    Validation --> Memory
    Memory --> Disk

    Validation --> Parser
    Parser --> Indexer
    Indexer --> Analytics

    %% Cache Flow
    Memory --> Invalidation
    Disk --> Invalidation

    %% Styling
    classDef source fill:#ffecb3
    classDef load fill:#e1f5fe
    classDef cache fill:#f3e5f5
    classDef process fill:#e8f5e8

    class GitHub,Official,APIs source
    class Loaders,HTTP,Validation load
    class Memory,Disk,Invalidation cache
    class Parser,Indexer,Analytics process
```

**Service Architecture Code Pattern**:
```python
class ContentService:
    async def get_document(self, type: str, filename: str) -> Dict
    async def search_documents(self, query: str) -> List[Dict]
    async def get_framework_data(self, framework_id: str) -> Dict
```

**Content Sources**:
- Local file system (legacy FINOS content)
- Remote APIs (official framework sources)
- Cached content store
- Dynamic loader services

## Data Models

### Framework Model

```python
@dataclass
class Framework:
    id: str
    name: str
    description: str
    type: FrameworkType  # ACTIVE, MODELED
    version: str
    last_updated: datetime
    references: List[FrameworkReference]
    categories: List[str]
    compliance_metrics: ComplianceMetrics
```

### Framework Reference

```python
@dataclass
class FrameworkReference:
    id: str
    title: str
    content: str
    category: str
    severity: SeverityLevel
    compliance_status: ComplianceStatus
    tags: List[str]
    related_controls: List[str]
```

### Search Result

```python
@dataclass
class FrameworkSearchResult:
    framework: str
    reference_id: str
    title: str
    content: str
    relevance_score: float
    severity: SeverityLevel
    compliance_status: ComplianceStatus
    highlights: List[str]
```

## Integration Patterns

### 1. Tool Integration Pattern

All framework tools follow a consistent pattern:

```python
async def handle_framework_tool(name: str, arguments: dict) -> List[TextContent]:
    # 1. Initialize framework components
    await _ensure_framework_components()

    # 2. Validate input arguments
    validated_args = validate_arguments(arguments)

    # 3. Execute framework operation
    result = await _framework_operation(validated_args)

    # 4. Format and return response
    return format_response(result)
```

### 2. Caching Strategy

**Multi-Level Caching**:
- **L1**: In-memory framework data cache
- **L2**: Query result cache with TTL
- **L3**: Persistent disk cache for expensive operations

**Cache Invalidation**:
- Time-based expiration (TTL)
- Content-based invalidation
- Manual cache refresh capabilities

### 3. Error Handling Pattern

**Graceful Degradation**:
```python
try:
    # Primary operation
    result = await primary_framework_operation()
except FrameworkUnavailableError:
    # Fallback to cached data
    result = await get_cached_framework_data()
except Exception as e:
    # Return structured error response
    return create_error_response(e)
```

## Security Architecture

### 1. Input Validation

**Multi-Layer Validation**:
- Schema validation using Pydantic models
- SQL injection prevention
- Path traversal protection
- Content size limits

### 2. Rate Limiting

**Sliding Window Algorithm**:
- Per-client rate limiting
- Different limits for different tool categories
- Circuit breaker for overloaded services

### 3. Content Security

**Safe Content Handling**:
- Content sanitization for external sources
- File type validation
- Size limits enforcement
- Dangerous pattern detection

## Performance Characteristics

### Response Time Targets

| Operation Type | Target Time | Cache Hit | Cache Miss |
|----------------|-------------|-----------|------------|
| Framework List | <50ms | <10ms | <100ms |
| Simple Search | <200ms | <50ms | <500ms |
| Complex Query | <1s | <200ms | <2s |
| Export Operation | <5s | <1s | <10s |

### Scalability Metrics

- **Concurrent Users**: 100+ simultaneous connections
- **Request Throughput**: 1000+ requests/minute
- **Memory Usage**: <500MB base, <2GB peak
- **Framework Count**: Supports 10+ frameworks simultaneously

### Caching Performance

- **Cache Hit Rate**: >95% for framework data
- **Query Cache**: >80% hit rate for common searches
- **Memory Efficiency**: LRU eviction with size limits

## Extension Points

### 1. Adding New Frameworks

**Implementation Steps**:
1. Create framework data model
2. Implement data loader for framework
3. Add framework to supported list
4. Update cross-framework mappings
5. Add framework-specific tests

**Framework Loader Interface**:
```python
class CustomFrameworkLoader:
    async def load_framework_data(self) -> Framework
    async def refresh_data(self) -> bool
    def get_framework_metadata(self) -> FrameworkMetadata
```

### 2. Custom Tool Development

**Tool Development Pattern**:
```python
# 1. Define tool schema
CUSTOM_TOOL = Tool(
    name="custom_operation",
    description="Custom framework operation",
    inputSchema=custom_schema
)

# 2. Implement handler
async def handle_custom_tool(arguments: dict) -> List[TextContent]:
    # Tool implementation
    pass

# 3. Register with system
FRAMEWORK_TOOLS.append(CUSTOM_TOOL)
TOOL_HANDLERS["custom_operation"] = handle_custom_tool
```

### 3. Content Source Integration

**Adding New Content Sources**:
```python
class CustomContentProvider:
    async def fetch_content(self, identifier: str) -> Dict
    async def search_content(self, query: str) -> List[Dict]
    def get_content_metadata(self) -> ContentMetadata
```

## Monitoring and Observability

### 1. Health Monitoring

**Service Health Checks**:
- Framework loader health
- Content service availability
- Cache performance metrics
- External API connectivity

### 2. Performance Metrics

**Key Performance Indicators**:
- Response time percentiles (P50, P95, P99)
- Error rates by tool type
- Cache hit rates
- Framework load times

### 3. Logging and Tracing

**Structured Logging**:
- Request/response logging
- Performance metrics
- Error tracking
- Security event logging

**Correlation IDs**:
- Request tracing across components
- Cross-framework operation tracking
- Error correlation and debugging

## Configuration Management

### 1. Framework Configuration

```yaml
frameworks:
  nist_ai_rmf:
    enabled: true
    source: "official_api"
    cache_ttl: 3600
    refresh_interval: 86400

  custom_framework:
    enabled: true
    source: "file_system"
    path: "/data/custom"
```

### 2. Performance Tuning

```yaml
performance:
  cache:
    max_memory: "256MB"
    ttl_default: 3600

  rate_limiting:
    tool_calls: 50
    resource_access: 200

  timeouts:
    framework_load: 30
    search_operation: 10
```

### 3. Security Settings

```yaml
security:
  validation:
    max_query_length: 1000
    max_result_size: "50MB"

  rate_limiting:
    enabled: true
    window_seconds: 60
```

This architecture provides a robust, scalable foundation for governance framework operations while maintaining security, performance, and extensibility requirements.
