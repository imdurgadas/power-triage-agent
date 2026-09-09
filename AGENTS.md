# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Overview

**IBM Power Porting Triage Agent** is an agentic AI prototype that automates the assessment of enterprise workload migration readiness to IBM Power (`ppc64le`) architecture. The system performs intelligent multi-source availability lookups, recursive transitive dependency analysis, architecture-specific code heuristics (SIMD/AVX, 64KB page size, inline assembly), and generates executive sales qualification deliverables.

### Core Capabilities

1. **Universal Ingestion**: Parses SBOMs (CycloneDX, SPDX), Dockerfiles, language manifests (requirements.txt, package.json, pom.xml, go.mod), and freeform text
2. **Multi-Source Probing**: Queries Docker Hub, Quay.io, RHEL/Ubuntu package repositories, PyPI, and IBM Power ecosystem databases
3. **Transitive Dependency Analysis**: Recursively scopes build-time dependencies and computes compounded porting effort
4. **Architecture Sensitivity Detection**: Identifies x86 SIMD/AVX instructions, inline assembly, and 64KB page size issues
5. **Agentic AI Orchestration**: Uses Google Gemini API with function calling for intelligent reasoning and synthesis
6. **Executive Reporting**: Generates readiness scores, effort estimates (person-days), and pre-sales qualification memos

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                                    │
│  - Real-time agent reasoning stream (SSE)                   │
│  - Interactive dependency tables with drill-down            │
│  - Executive scorecard & export capabilities                │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / Server-Sent Events
┌────────────────────────▼────────────────────────────────────┐
│  Backend (FastAPI + Python)                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 1. Universal Normalizer (PURL, SBOM, Docker, Python)  │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ 2. Multi-Source Prober (Registries, Repos, PyPI)      │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ 3. Build Analyzer (Transitive deps, SIMD detection)   │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ 4. Repo Scanner (Git clone, Dockerfile/CI analysis)   │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ 5. Agentic AI Layer (Gemini Tool Calling + Synthesis) │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- Python 3.9+ with FastAPI and Uvicorn
- Pydantic for data validation and serialization
- Google GenAI SDK (`google-genai`) for Gemini API integration
- httpx for async HTTP requests to registries
- PyYAML for configuration parsing

**Frontend:**
- React 18.3+ with Vite build system
- Lucide React for icons
- Custom CSS design system (IBM Carbon-inspired dark theme)
- Server-Sent Events (SSE) for real-time streaming

**Deployment:**
- Docker containerization for both frontend and backend
- Docker Compose orchestration with health checks
- Nginx for frontend static file serving

## Building and Running

### Prerequisites

- Docker and Docker Compose installed
- Google Gemini API key (optional - system runs in simulation mode without it)

### Environment Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Configure your Gemini API key in `.env`:
   ```bash
   GEMINI_API_KEY=your_actual_api_key_here
   GEMINI_MODEL=gemini-3.5-flash
   ```

   **Note:** The system will run in "autonomous simulation mode" if no API key is provided, faithfully emulating multi-step tool calling and streaming thought steps.

### Running with Docker (Recommended)

Start the entire stack:
```bash
docker-compose up --build
```

Or use the convenience scripts:
```bash
./docker-start.sh   # Start services
./docker-stop.sh    # Stop services
```

**Access Points:**
- Frontend: http://localhost:5173 or http://localhost:80
- Backend API: http://localhost:8000
- API Health Check: http://localhost:8000/api/health
- API Documentation: http://localhost:8000/docs

### Local Development (Without Docker)

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Running Tests

Backend unit tests:
```bash
cd backend
pytest
```

## Development Conventions

### Code Organization

**Backend Structure:**
- `main.py`: FastAPI application entry point, API endpoints
- `agent.py`: Core agentic orchestrator with Gemini function calling
- `models.py`: Pydantic schemas for requests, responses, and domain objects
- `normalizer.py`: Universal manifest parser (SBOM, Dockerfile, language manifests)
- `prober.py`: Multi-source availability engine (Docker Hub, package repos, PyPI)
- `build_analyzer.py`: Transitive dependency resolver and architecture heuristics
- `repo_scanner.py`: Git repository cloning and analysis (Dockerfiles, CI configs)
- `gemini_helper.py`: Gemini API interaction utilities
- `tests/`: Unit and integration tests

**Frontend Structure:**
- `src/App.jsx`: Main application component
- `src/components/`: Reusable UI components
  - `InputSection.jsx`: Tabbed input with sample workload loaders
  - `AgentLiveFeed.jsx`: Real-time agent execution stream
  - `Scorecard.jsx`: Executive metrics dashboard
  - `DependencyTable.jsx`: Interactive package analysis table
  - `CodeAuditModal.jsx`: Architecture sensitivity deep-dive
  - `ExportModal.jsx`: Report generation and export

### Key Design Patterns

1. **Streaming Architecture**: Backend uses async generators to yield real-time agent steps via Server-Sent Events (SSE)

2. **Pydantic Models**: All data structures use Pydantic for validation, serialization, and API documentation

3. **Multi-Source Probing**: Availability checks follow a tiered approach:
   - Tier 1: Native ppc64le packages in official repos
   - Tier 2: Platform-agnostic (scripts, bytecode)
   - Tier 3: Substitute packages available
   - Tier 4: Unported (requires source build)
   - Tier 5: Blocker (proprietary x86 dependencies)

4. **Effort Calculation**: Compounded person-day estimates using formula:
   ```
   Total Effort = Base Build + Σ(Unported Build Deps) + Arch Complexity + Test Validation
   ```

5. **SIMD Complexity Tiers**: Four-tier classification for x86 SIMD porting:
   - `direct`: Simple macro drop-in replacements
   - `simde_compatible`: SIMDe header library mapping
   - `partial_rewrite`: Mixed intrinsics requiring VSX rewrite
   - `full_redesign`: Deep AVX-512 dependencies

### Architecture Sensitivity Detection

The system scans for three categories of architecture-specific code:

1. **SIMD/AVX Instructions**: `<immintrin.h>`, `_mm256_*`, `_mm512_*`, AVX2 compiler flags
2. **Inline Assembly**: `__asm__`, `rdtsc`, `cpuid`, x86-specific registers
3. **64KB Page Size Issues**: Memory alignment, jemalloc/rocksdb allocators

### API Endpoints

- `GET /api/health`: Health check endpoint
- `GET /api/sample-workloads`: Returns curated demo workloads
- `POST /api/triage`: Synchronous triage analysis (returns final result)
- `POST /api/triage/stream`: Streaming triage with real-time agent steps (SSE)

### Error Handling

- Backend uses FastAPI's HTTPException for API errors
- Gemini API failures gracefully fall back to simulation mode
- All external API calls (Docker Hub, PyPI) include timeout and retry logic
- Frontend displays user-friendly error messages with recovery suggestions

### Logging

- Backend uses Python's standard logging module
- Log levels: INFO for normal operations, WARNING for fallbacks, ERROR for failures
- Structured logging for agent steps and tool executions

## Important Context for AI Agents

### When Modifying the Agentic Pipeline

1. **Agent Steps**: All agent reasoning must be yielded as `AgentStep` objects with:
   - `step_id`: Sequential counter
   - `agent_name`: Logical agent role (e.g., "AvailabilityProber", "BuildScopingAgent")
   - `action_type`: One of "plan", "lookup", "scan", "deep_scan", "llm_reasoning", "synthesis"
   - `thought`: Human-readable reasoning
   - `detail`: Optional supporting evidence

2. **Streaming Protocol**: Use async generators with `yield` to emit events:
   ```python
   yield {"type": "step", "step": agent_step.model_dump()}
   yield {"type": "result", "data": final_response.model_dump()}
   ```

3. **Gemini Function Calling**: Tools must be defined with clear schemas and the agent must parse function call responses correctly

### When Adding New Package Ecosystems

1. Update `normalizer.py` to parse the new manifest format
2. Add probing logic in `prober.py` for the ecosystem's registry
3. Update `BuildAnalyzer` if the ecosystem has unique build patterns
4. Add test cases in `backend/tests/`

### When Extending Architecture Heuristics

1. Add detection patterns in `build_analyzer.py`
2. Update `ArchSensitivity` model in `models.py` with new fields
3. Adjust effort multipliers in `scale_arch_effort()` function
4. Update frontend to display new sensitivity indicators

### Sample Workloads

The system includes four curated demo workloads:
1. **Enterprise Cloud Microservices**: Standard containerized stack (Nginx, Redis, PostgreSQL, Kafka, Node.js, Spring Boot)
2. **AI/ML Data Pipeline**: PyTorch, NumPy, FastAPI with custom C++ vector kernel
3. **High-Throughput Storage Engine**: RocksDB, simdjson with 64KB page sensitivities
4. **Legacy Financial Analytics**: Intel MKL blocker scenario

These are accessible via `/api/sample-workloads` and serve as integration test fixtures.

### Security Considerations

- API keys should never be committed to the repository
- Use `.env` files for local development (excluded via `.gitignore`)
- Docker secrets or environment variables for production deployment
- CORS is currently configured for development (`allow_origins=["*"]`) - restrict in production

### Performance Notes

- Shallow Git clones are used for repository scanning to minimize disk I/O
- Temporary repositories are cleaned up after analysis
- HTTP requests to registries use connection pooling via httpx
- Frontend uses React's built-in optimizations (no additional state management needed for this prototype)

## Troubleshooting

**Backend won't start:**
- Verify Python 3.9+ is installed
- Check that all dependencies in `requirements.txt` are installed
- Ensure port 8000 is not already in use

**Frontend build fails:**
- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Verify Node.js version is 18+

**Gemini API errors:**
- Verify API key is correctly set in `.env`
- Check API quota limits in Google Cloud Console
- System will automatically fall back to simulation mode if API is unavailable

**Docker Compose issues:**
- Ensure Docker daemon is running
- Check logs: `docker-compose logs backend` or `docker-compose logs frontend`
- Rebuild containers: `docker-compose up --build --force-recreate`
