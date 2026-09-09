# Implementation Plan: IBM Power Porting Triage Agent Prototype

Build an end-to-end, agentic AI prototype that assesses enterprise workload readiness for migration to **IBM Power (`ppc64le`)**, automates multi-source availability lookups, recursively scopes build-time transitive dependencies for unported packages, applies architecture-specific code heuristics (SIMD, 64KB page size, assembly), and generates executive sales qualification deliverables.

## Proposed Architecture Overview

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                    Modern Pre-Sales Executive UI                       │
 │  - Tabbed Ingestion (SBOM, Dockerfiles, Git URLs, Freeform Text)      │
 │  - Real-time Agent Reasoning & Tool Execution Stream                   │
 │  - Executive Feasibility Scorecard (Readiness %, Effort Range, Go/No-Go)│
 │  - Transitive Build-Dependency Iceberg Visualizer                      │
 │  - Interactive Code Audit Drawer (x86 SIMD -> SIMDe / VSX remediations) │
 │  - One-Click Exports (Executive 1-Pager PDF/MD, JIRA/CSV Backlog)      │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP / SSE Stream
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │                      FastAPI Backend Engine                            │
 │  ┌──────────────────────────────────────────────────────────────────┐  │
 │  │ 1. Universal Ingestion & Normalizer (PURL, SBOM, Docker, Python)  │  │
 │  ├──────────────────────────────────────────────────────────────────┤  │
 │  │ 2. Multi-Source Prober (Docker Hub, RHEL/Ubuntu Ports, PyPI)     │  │
 │  ├──────────────────────────────────────────────────────────────────┤  │
 │  │ 3. Transitive Build-Dependency Engine (Extracts BuildRequires)   │  │
 │  ├──────────────────────────────────────────────────────────────────┤  │
 │  │ 4. Static Heuristic Scanner (x86 SIMD, inline asm, 64KB pages)   │  │
 │  ├──────────────────────────────────────────────────────────────────┤  │
 │  │ 5. Agentic AI Layer (Gemini Tool Calling + Reasoning Synthesizer)│  │
 │  └──────────────────────────────────────────────────────────────────┘  │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## User Review Required

> [!IMPORTANT]
> **LLM API Configuration:** The backend will support live **Google Gemini API** (using `GEMINI_API_KEY` configured in `.env` or input directly in the UI). To guarantee that the prototype runs immediately even before an API key is provided, the backend will feature a full **Agentic Simulation Mode** that faithfully emulates multi-step tool calling, registry probing, and streaming thought steps.

> [!NOTE]
> **Technology Stack:**
> - **Backend:** Python 3.9+ with FastAPI, Uvicorn, Pydantic, httpx, and Google GenAI SDK.
> - **Frontend:** Vite + React with custom Vanilla CSS design system (IBM Carbon-inspired theme, rich dark mode, glassmorphism, responsive data tables, visual dependency tree).

---

## Proposed Changes

### Backend (`backend/`)

#### [NEW] [backend/requirements.txt](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/requirements.txt)
Dependencies: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `python-dotenv`, `google-genai`, `jinja2`.

#### [NEW] [backend/models.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/models.py)
Pydantic schemas for:
- `TriageRequest`: Input manifests, raw text, git URLs, target OS (`rhel8`, `rhel9`, `ubuntu22`, `ubuntu24`, `sles15`), platform (`baremetal`, `powervm`, `ocp`), triage depth (`express` vs `deep`).
- `BuildDependency`: Represents transitive build requirements (`name`, `version`, `status`, `effort_pd`, `source`).
- `PackageTriageResult`: Target package status, tier (Native, Script, Unported, Blocker), direct evidence links, build toolchain requirements (e.g. Bazel, GCC version), transitive build dependencies, architecture flags (SIMD/AVX, assembly, 64k pages), and person-day effort estimate.
- `TriageResponse`: Overall readiness score (0-100%), recommendation (`GO`, `CAUTION`, `HIGH_RISK`), total person-day range (min/max), component breakdown, and executive summary.

#### [NEW] [backend/normalizer.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/normalizer.py)
Parser supporting:
- SBOMs (CycloneDX JSON, SPDX JSON).
- Container files (`Dockerfile`, `docker-compose.yml`).
- Language manifests (`requirements.txt`, `package.json`, `pom.xml`, `go.mod`).
- Unstructured freeform text extraction (extracts package names and version hints).

#### [NEW] [backend/prober.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/prober.py)
Multi-source availability engine:
- Docker Hub API v2 & Quay.io: inspects multi-arch manifest lists for `linux/ppc64le`.
- Linux Distro package indexes (RHEL 8/9 ppc64le, Ubuntu Ports `main`/`universe`).
- Language registries: PyPI API (checking `ppc64le` wheel tags vs `none-any`).
- IBM Power Ecosystem DB: Open-CE, Power DevOps catalog, community recipes.

#### [NEW] [backend/build_analyzer.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/build_analyzer.py)
The **Transitive Source Build & Heuristic Engine**:
- Resolves build systems (`CMake`, `Meson`, `setup.py`, `Cargo`, `Bazel`).
- Extracts `BuildRequires` (development headers, link-time native dependencies).
- Checks build toolchain readiness on Power (e.g., Bazel ppc64le availability).
- Scans for architecture sensitivity:
  - x86 SIMD/AVX: `<immintrin.h>`, `_mm256_*`, `_mm512_*`, AVX2 flags.
  - Inline assembly: `__asm__`, `rdtsc`, `cpuid`.
  - 64KB page size issues: memory buffer alignment, jemalloc/rocksdb allocators.
- Computes compounded effort using:
  $$\text{Total Effort} = \text{BaseBuildEffort} + \sum \text{Effort}(\text{UnportedBuildDeps}) + \text{ArchComplexity} + \text{Validation}$$

#### [NEW] [backend/agent.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/agent.py)
Agentic LLM orchestrator:
- Implements Gemini function calling with tools:
  - `probe_multi_source_availability`
  - `analyze_source_build_and_dependencies`
  - `search_ppc64le_community_patches`
  - `recommend_substitutes_and_remediations`
- Produces live streaming agent steps (SSE) and structured final synthesis.

#### [NEW] [backend/main.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/main.py)
FastAPI app exposing `/api/triage`, `/api/triage/stream`, `/api/health`, and sample workloads.

---

### Frontend (`frontend/`)

#### [NEW] [frontend/package.json](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/package.json)
Vite + React setup with Lucide icons.

#### [NEW] [frontend/src/index.css](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/index.css)
Comprehensive design system:
- High-contrast sleek dark theme (`#0c101c`, `#161e31`, `#222f4c`).
- IBM Blue accents (`#0f62fe`, `#4589ff`), Cyber Cyan (`#11c2d4`), Success Green (`#24a148`), Warning Amber (`#f1c21b`), Blocker Crimson (`#da1e28`).
- Glassmorphism, smooth animations, and clean typography.

#### [NEW] [frontend/src/components/InputSection.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/InputSection.jsx)
Tabbed input hub with sample workload quick-loaders:
1. *Enterprise Microservices Stack* (Mixed Docker + Redis + Nginx + Java + Python)
2. *AI/ML Ingest Pipeline* (PyTorch + Custom C++ SIMD extension + Kafka)
3. *Custom Legacy C/C++ Workload* (Unported library with 3 transitive build dependencies)
File upload (drag and drop SBOM/Dockerfile), target OS selectors, and triage depth toggle.

#### [NEW] [frontend/src/components/AgentLiveFeed.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/AgentLiveFeed.jsx)
Visual agentic execution stream showing real-time tool calls, thoughts, and discoveries.

#### [NEW] [frontend/src/components/Scorecard.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/Scorecard.jsx)
Executive metric cards: Readiness Score gauge, Traffic light recommendation badge, Total Person-Days range, and component breakdown stats.

#### [NEW] [frontend/src/components/DependencyTable.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/DependencyTable.jsx)
Interactive table with search/filtering, evidence tags, drill-down expandable rows showing **transitive build dependencies** and architecture sensitivity badges.

#### [NEW] [frontend/src/components/CodeAuditModal.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/CodeAuditModal.jsx)
Deep-dive drawer showing flagged x86 SIMD/assembly snippets and proposed `SIMDe` / VSX mitigation.

#### [NEW] [frontend/src/components/ExportModal.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/ExportModal.jsx)
One-click pre-sales Executive 1-Pager memo generator and JIRA/CSV backlog exporter.

---

## Verification Plan

### Automated Tests
1. **Backend Unit Tests (`backend/tests/`):**
   - Manifest parsing test: parse CycloneDX SBOM, Dockerfile, and `requirements.txt`.
   - Availability prober test: verify Docker Hub multi-arch check and PyPI ppc64le check.
   - Transitive build resolver test: verify recursive build-dependency effort compounding calculation.
   - Run tests via `pytest`.

2. **End-to-End API Test:**
   - POST to `/api/triage` with sample enterprise workloads and verify JSON response schema integrity.

### Manual Verification
1. Launch backend on `localhost:8000` and frontend on `localhost:5173`.
2. Test sample workloads (Enterprise Microservices, AI/ML, Unported C++ Library with build dependencies).
3. Verify live streaming agentic reasoning steps.
4. Verify drill-down into transitive build-time dependencies.
5. Verify export of Executive 1-Pager.
