# Walkthrough: IBM Power Porting Triage Agent Prototype

We have built and verified the **IBM Power Porting Triage Agent**, an agentic AI prototype designed for technical pre-sales and solution architects to qualify customer application migrations to **IBM Power (`ppc64le`)**.

---

## 1. What Was Built

### A. Realistic Transitive Build Dependency & Sizing Engine (`backend/`)
- **Universal Manifest Normalizer ([backend/normalizer.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/normalizer.py)):**
  Parses mixed enterprise inputs: CycloneDX/SPDX SBOMs, Dockerfiles, Python `requirements.txt`, Node.js `package.json`, Java `pom.xml`, and free-form client emails or stack descriptions into normalized Package URLs (`purl`).
- **Multi-Source Availability Prober ([backend/prober.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/prober.py)):**
  Inspects multi-arch manifests across container registries (Docker Hub, Quay), OS repositories (RHEL 8/9 ppc64le BaseOS/AppStream, EPEL, Ubuntu Ports), language registries (PyPI ppc64le wheels vs `none-any.whl`, Maven, NPM), and IBM-specific sources (ICR `ppc64le-oss`, `ppc64le/build-scripts`, `ppc64le/pyeco` DevPi).

  **Source precedence policy:** Red Hat distro repositories (RHEL/EPEL Koji) and Docker Hub / Quay are probed first and take precedence over IBM-specific sources. IBM Container Registry (`icr.io/ppc64le-oss`), `ppc64le/build-scripts` recipes, and IBM pyeco DevPi wheels are used only as fallbacks when no upstream distro or public registry result is found. This ensures the most broadly maintained and canonical upstream package is always preferred.

  Probe order:
  1. RHEL/EPEL Koji (Red Hat distro RPMs)
  2. Docker Hub / Quay.io live multi-arch manifest check
  3. PyPI live API (ppc64le wheels / noarch)
  4. ppc64le/pyeco DevPi wheels index *(IBM fallback, Python only)*
  5. IBM Container Registry ppc64le-oss *(IBM fallback, containers only)*
  6. ppc64le/build-scripts build recipe index *(IBM fallback, any ecosystem)*
  7. Static curated cache (blockers, math libs, unmaintained entries)
  8. Gemini LLM research
- **Transitive Source Build & Heuristic Engine ([backend/build_analyzer.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/build_analyzer.py)):**
  - **The "Dependency Iceberg" Scope:** When a package is unported, inspects build systems (CMake, Make, Bazel, setup.py) and extracts **Build-Time Requirements (`BuildRequires`)**.
  - **Recursive Availability Probing:** Checks if the build requirements are available in the target OS. If a build dependency is *also* missing (e.g., `jemalloc-ppc64le` for RocksDB), it is flagged as an unported transitive dependency with its own porting effort.
  - **Architecture Code Sensitivity Scanner:** Audits for x86 SIMD/AVX (`<immintrin.h>`, `__AVX2__`), inline assembly (`__asm__`, `cpuid`), and **64KB memory page-size constraints** (vs x86 4KB). Formulates concrete remediation strategies (e.g. `SIMDe` translation headers or Power VSX intrinsics).
  - **Compounded Effort Formula:**
    $$\text{Total Effort} = \text{BaseBuildEffort} + \sum \text{Effort}(\text{UnportedBuildDeps}) + \text{ArchComplexity} + \text{Validation}$$
- **Agentic AI Orchestrator ([backend/agent.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/agent.py)):**
  Streams live agentic reasoning steps (SSE) and synthesizes executive sales qualification briefs. Supports live Gemini API (`GEMINI_API_KEY`) as well as autonomous simulation mode.
- **FastAPI Server ([backend/main.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/main.py)):**
  Exposes `/api/health`, `/api/sample-workloads`, `/api/triage`, and `/api/triage/stream`.

---

### B. Pre-Sales Executive User Interface (`frontend/`)
- **IBM Carbon-Inspired Dark UI:** Built with Vite and modern Vanilla CSS (`frontend/src/index.css`), featuring high-contrast metrics, glassmorphic cards, and status tags.
- **Input Parameters & Presets ([frontend/src/components/InputSection.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/InputSection.jsx)):**
  - Instant demo test presets:
    1. *Enterprise Cloud Microservices* (Nginx, Redis, Postgres, Kafka, Node.js, Spring Boot)
    2. *AI/ML Data Pipeline* (PyTorch, NumPy, Pandas, FastAPI, Custom C++ AVX2 Kernel)
    3. *High-Throughput Storage Engine* (RocksDB + simdjson demonstrating the dependency iceberg and 64KB page allocator requirements)
    4. *Legacy Financial Analytics* (x86 blocker detection with Intel MKL and alternative recommendations)
  - Target OS selection (RHEL 8/9, Ubuntu 22/24, SLES 15), platform selection (OCP, PowerVM, Bare Metal), and triage depth mode.
- **Live Agent Execution Feed ([frontend/src/components/AgentLiveFeed.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/AgentLiveFeed.jsx)):**
  Displays real-time agent thoughts, registry lookups, build-tree expansions, and discoveries.
- **Executive Feasibility Scorecard ([frontend/src/components/Scorecard.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/Scorecard.jsx)):**
  Porting Readiness Score (%), Traffic Light recommendation badge (🟢 **GO**, 🟡 **CAUTION**, 🔴 **HIGH_RISK**), Total Person-Days Sizing range, and Scoped Transitive Build Requirements count.
- **Dependency & Build-Tree Matrix ([frontend/src/components/DependencyTable.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/DependencyTable.jsx)):**
  Filterable table with expandable rows revealing the nested build-time dependencies, toolchains, and effort tags.
- **Architecture Code Audit Modal ([frontend/src/components/CodeAuditModal.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/CodeAuditModal.jsx)):**
  Displays flagged source code patterns and recommended Power VSX / SIMDe fixes.
- **Deliverables Exporter ([frontend/src/components/ExportModal.jsx](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/src/components/ExportModal.jsx)):**
  One-click export of the Executive 1-Pager memo (Markdown) and engineering backlog (CSV).

---

## 2. Validation & Test Results

### Automated Test Suite
- Executed `PYTHONPATH=. backend/.venv/bin/pytest backend/tests/`:
  - `test_health`: Verified `/api/health` returns `{"status": "ok"}`.
  - `test_sample_workloads`: Verified preset workloads.
  - `test_normalizer_dockerfile`, `test_normalizer_requirements`, `test_normalizer_sbom`: Verified manifest ingestion.
  - `test_prober_known`: Verified Docker Hub multi-arch check and PyPI wheel detection.
  - `test_build_analyzer_unported_transitive_deps`: **Verified recursive build-dependency scoping for unported packages (`rocksdb` -> `jemalloc-ppc64le`), 64KB page-size risk detection, and compounded person-day calculation.**
  - `test_api_triage_flow`: Verified end-to-end API pipeline.
- **Result:** **8 passed in 1.35s (100% pass rate).**

### API & Live SSE Streaming Verification
- Tested `/api/triage/stream` with curl: verified real-time Server-Sent Events (`IngestionAgent` $\rightarrow$ `AvailabilityProber` $\rightarrow$ `BuildScopingAgent` $\rightarrow$ `ExecutiveSynthesizer`).
- Tested `rocksdb` workload: verified that `jemalloc-ppc64le` was scoped as an unported build requirement (+1.5 PD) with 64KB page size risk (+1.5 PD), bringing total effort to 4.5 Person-Days.
- Frontend production build (`npm run build`) succeeded with 0 errors.

---

## 3. Docker Containerization & GEMINI_API_KEY Integration

### Container Architecture:
- **Backend Service ([backend/Dockerfile](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/Dockerfile)):**
  - Python 3.11-slim container.
  - Automatically loads `GEMINI_API_KEY` from environment / `.env`.
  - Exposes port `8000` with healthchecks on `/api/health`.
- **Frontend Service ([frontend/Dockerfile](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/Dockerfile) & [frontend/nginx.conf](file:///Users/durgadas/code/ccaf/gemini-elite-ai/frontend/nginx.conf)):**
  - Multi-stage build (`node:20-alpine` builds Vite assets, `nginx:alpine` serves them).
  - Nginx reverse-proxies `/api/` requests to `http://backend:8000/api/` with streaming SSE headers (`proxy_buffering off;`, `chunked_transfer_encoding on;`).
  - Exposes ports `5173:80` and `80:80`.
- **Orchestrator ([docker-compose.yml](file:///Users/durgadas/code/ccaf/gemini-elite-ai/docker-compose.yml)):**
  - Connects frontend and backend on internal bridge network `triage-net`.
  - Passes `GEMINI_API_KEY=${GEMINI_API_KEY:-}` to containers.
- **Convenience Scripts:**
  - Bring up: `./docker-start.sh` (or `docker compose up -d --build`)
  - Bring down: `./docker-stop.sh` (or `docker compose down`)
  - Environment template: [.env.example](file:///Users/durgadas/code/ccaf/gemini-elite-ai/.env.example)

### GEMINI_API_KEY Usage in Code:
1. **Dynamic Architecture Analysis ([backend/agent.py](file:///Users/durgadas/code/ccaf/gemini-elite-ai/backend/agent.py)):**
   - When architecture friction (x86 SIMD / AVX, inline assembly, 64KB page size) is discovered in unported components, the agent invokes Gemini (`gemini-2.5-flash`) via the `google-genai` SDK to evaluate the code snippet and generate exact Power VSX / SIMDe translation instructions.
2. **AI-Powered Executive Sales Synthesis:**
   - The agent calls Gemini to draft a strategic, tailored pre-sales proposal highlighting IBM Power's hardware advantages (SMT8 threading, memory bandwidth, Open-CE) tailored to the specific customer workload.
3. **Graceful Autonomous Fallback:**
   - If `GEMINI_API_KEY` is not provided or offline, the engine automatically uses the built-in deterministic porting knowledge base without crashing.
