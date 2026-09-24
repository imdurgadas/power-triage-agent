# IBM Power Porting Triage Agent — Submission Brief

**AI Elite Program — Prototype Submission**  
**Target Architecture:** IBM Power (`ppc64le`) | RHEL 8/9, OpenShift OCP, Ubuntu, SLES  
**Submission Category:** Autonomous AI Agent Prototype

---

## 1. The Problem

IBM Power hardware delivers transformative performance advantages — industry-leading memory bandwidth, SMT8 multi-threading (up to 8 threads per core), and hardware Matrix Math Accelerators (MMA) for AI inference. Yet migrating enterprise application stacks from commodity x86 infrastructure to Power consistently stalls before it starts, because no one can quickly and reliably answer a single question:

> *"Will our software stack run on IBM Power, and what is the exact engineering effort required to port what doesn't?"*

Today, answering that question creates severe, compounding friction across the pre-sales pipeline:

### 1.1 Fragmented and Heterogeneous Customer Inputs

Customers arrive with dependency specifications in wildly different formats: CycloneDX / SPDX SBOM JSON files, multi-stage Dockerfiles, Python `requirements.txt`, Maven `pom.xml`, informal meeting notes, or a bare GitHub repository URL. Each format requires specialist knowledge to parse, normalise, and reason about. No standardised intake exists.

### 1.2 Fragmented Ecosystem Registries and Version Drift

Determining ppc64le availability requires manual, error-prone searches across multiple distinct registries: RHEL 8/9 BaseOS, AppStream, and EPEL, Quay.io, Docker Hub, PyPI, Conda-Forge, and IBM Open-CE. A positive result at one registry is insufficient — the customer's *specific version tag* frequently lacks a ppc64le binary even when adjacent versions are available, producing false confidence and downstream project failures.

### 1.3 The "Dependency Iceberg" — Hidden Build-Time Costs

When a C/C++ library or database engine has no prebuilt ppc64le binary, the triage task does not end there. Beneath every such package lies a tree of build-time dependencies (CMake modules, header libraries, memory allocators, compression codecs) that must *also* be available and correctly tuned for Power. These hidden layers routinely surface only after porting has begun, causing costly overruns and customer dissatisfaction. A typical example: **RocksDB** lacks a ppc64le binary, but its build dependency **jemalloc** also requires explicit 64KB memory-page configuration (`--with-lg-page=16`) on Power — a non-obvious, second-level blocker.

### 1.4 Opaque and Inaccurate Effort Sizing

Pre-sales engineers currently estimate porting timelines by gut feel, typically producing 2×–5× variance between estimates and actuals. There is no transparent, reproducible formula that accounts for x86 SIMD instruction density, porting complexity tier, upstream CI posture, transitive build chain depth, and test validation requirements simultaneously.

### 1.5 Pipeline Impact

The combined effect is a **5-to-10 business day qualification cycle** of email exchanges, catalog lookups, and manual slide deck assembly before any customer commitment can be formed. Senior engineers in IBM's Power Porting Lab absorb roughly 40% of their time performing this routine initial triage — capacity that should be reserved for hands-on porting work.

---

## 2. The Proposed Solution

The **Autonomous IBM Power Porting Triage Agent** is an agentic AI system that combines deterministic ecosystem probing, recursive build-tree analysis, and LLM-powered executive synthesis to deliver an authoritative, end-to-end migration qualification in under 30 seconds.

The system operates as a sequential autonomous agent pipeline with seven specialised stages:

1. **Universal Manifest Normaliser** — Accepts any combination of CycloneDX / SPDX SBOMs, Dockerfiles, `requirements.txt`, `pom.xml`, free-form email text, or raw GitHub / documentation URLs. Emits a canonical set of Package URLs (purls) as the unified working representation.

2. **Multi-Source Availability Prober** — Performs live version-aware queries against Docker Hub v2, Quay.io, RHEL/EPEL rpm metadata, PyPI wheel classifiers, Maven Central, and IBM Open-CE. Distinguishes between "exists for ppc64le at this version" and "exists for ppc64le at a different version," providing clickable evidence URLs and targeted upgrade/downgrade advice.

3. **Deep Build Dependency Scoper** — For every package flagged as unavailable, inspects the upstream build system (CMake, Make, Bazel, `setup.py`) and recursively extracts `BuildRequires`. Checks each build dependency for ppc64le availability in the target OS. If a build dependency is also missing, it is recursively scoped, producing a full transitive dependency graph with individual effort contributions at every node.

4. **Architecture Sensitivity Auditor** — Scans source code and headers for three categories of Power friction: (a) x86 SIMD intrinsics (`immintrin.h`, `__AVX2__`, AVX-512 calls), (b) inline assembly (`__asm__`, `cpuid`, `rdtsc`), and (c) memory allocators assuming 4 KB pages. Generates concrete remediation strategies — SIMDe header mappings, Power VSX intrinsic equivalents, and jemalloc page-size configuration flags.

5. **CI / Repository Posture Scanner** — Queries upstream Git repositories for existing Power markers (`#ifdef __powerpc__`, `ppc64le` CI runner entries) to produce a repo CI factor that modulates engineering effort upward or downward based on upstream willingness to accept Power patches.

6. **Transparent 3-Pillar Effort Sizing Engine** — Calculates a fully auditable effort estimate across Build, Engineering Adaptation, and Test Validation pillars, applying calibrated multipliers for SIMD volume brackets, porting complexity tiers, and repo CI posture. Final effort is rounded up to the next Fibonacci number, eliminating range estimates in favour of a single defensible ceiling figure.

7. **LLM Executive Synthesis** — When a Gemini API key is present, invokes Gemini 2.5 Flash to evaluate architecture friction snippets and produce a tailored, customer-facing executive qualification memo. The system degrades gracefully to a deterministic built-in knowledge base when the API is unavailable, ensuring zero runtime dependency for offline demos.

Deliverables generated autonomously at the end of every run include: an Executive Feasibility Scorecard (Porting Readiness %, qualification tier, single Fibonacci person-day sizing), a filterable Dependency and Build-Tree Matrix with expandable transitive nodes, an Architecture Code Audit report with remediation code, a one-click Executive PDF memo, and a JIRA-importable CSV engineering backlog.

---

## 3. Impact

| Dimension | Current State | With the Agent |
| :--- | :--- | :--- |
| **Qualification turnaround** | 5–10 business days of email exchanges and catalog lookups | < 30 seconds, fully automated |
| **Porting lab bandwidth** | ~40% of senior engineer time on routine initial triage | Zero routine triage; lab receives only pre-scoped engineering specs |
| **Effort sizing accuracy** | Subjective guesswork; 2×–5× variance | Transparent 3-pillar formula; single Fibonacci ceiling with full audit trail |
| **Deal velocity** | Extended sales cycles due to unknown porting risk | Immediate traffic-light readiness score during or immediately after the first customer call |
| **Executive deliverables** | Days assembling custom slide decks and proposal memos | One-click PDF executive memo and CSV backlog generated in-session |
| **Hidden-dependency exposure** | Transitive build deps surface after porting begins, causing overruns | Full dependency iceberg scoped recursively before any engineering work starts |

Across five validated enterprise scenarios — cloud microservices, AI/ML pipelines, high-throughput storage engines, legacy financial analytics, and direct URL ingestion — the agent produced accurate, auditable qualifications in under 30 seconds with 100% automated test coverage (8 tests, 1.35 s, 100% pass rate).

---

## 4. Technical Approach

### Hybrid Deterministic + Generative Architecture

The core design principle is that *deterministic probing governs correctness, and generative AI governs communication quality*. Registry lookups, build-tree traversal, SIMD scanning, and effort arithmetic are implemented as deterministic, testable Python modules with no LLM involvement. The LLM layer (Gemini 2.5 Flash) is invoked only at two narrow points: evaluating architecture friction snippets to produce exact remediation code, and synthesising the customer-facing executive narrative. This keeps the system's factual claims ground-truthed and auditable while making its outputs compelling and tailored.

### Streaming Agentic Execution

The backend exposes a Server-Sent Events (SSE) streaming endpoint (`/api/triage/stream`) so the frontend can display live agent reasoning steps — registry lookups, build-tree expansions, SIMD findings — as they occur. The four named agent stages (`IngestionAgent` → `AvailabilityProber` → `BuildScopingAgent` → `ExecutiveSynthesizer`) each emit structured step events, giving the user visibility into exactly what the system is doing and why.

### Deployment

The system is fully containerised: a FastAPI Python 3.11 backend and a Vite/React frontend served by Nginx (acting as a reverse proxy with SSE streaming headers configured). Both services are orchestrated via Docker Compose on an internal bridge network, with the Gemini API key injected through an environment variable. The frontend production build is zero-error and the full stack starts with a single `./docker-start.sh` command.

---

## 5. Key Innovations

Several design decisions distinguish this prototype from a conventional dependency-checker or LLM chat tool:

1. **Recursive Dependency Iceberg Scoping.**  
   Most tooling reports whether a package binary exists. This system goes further: for every missing binary it fetches the upstream build manifest, checks each build dependency for ppc64le availability, and recurses into any that are also missing. Each node in the transitive graph carries its own person-day contribution, producing a compounded effort formula:

   ```
   Total Effort = BaseBuildEffort + Σ Effort(UnportedBuildDeps) + ArchComplexity + Validation
   ```

2. **Calibrated 4-Tier SIMD Complexity Classification.**  
   Rather than treating all x86 SIMD as equally complex, the system classifies each case into `DIRECT`, `SIMDE_COMPATIBLE`, `PARTIAL_REWRITE`, or `FULL_REDESIGN` and applies a corresponding multiplier (1.0×–4.0×). A separate SIMD volume bracket (0–50, 51–200, 201–500, >500 instructions) further scales the estimate, making effort directly proportional to the actual code surface requiring inspection and replacement.

3. **Single-Value Fibonacci Sizing Ceiling.**  
   Conventional estimates expressed as ranges (e.g., "26–34 days") undermine customer trust because the two numbers invite negotiation and the upper bound is rarely defended. The agent computes a transparent maximum and rounds it to the next strictly greater Fibonacci number, yielding a single, defensible figure (e.g., 21 PD or 34 PD) that communicates a credible ceiling without false precision.

4. **64KB Memory Page-Size Awareness.**  
   Power runs a 64KB hardware page size versus x86's 4KB default. Memory allocators such as jemalloc assume 4KB pages; deploying them unmodified on Power results in silent corruption or crashes. The agent explicitly detects allocator usage in the build dependency chain and prescribes the correct `--with-lg-page=16` compile flag as part of the scoped engineering spec — a highly specific, non-obvious knowledge point absent from generic porting guides.

5. **Constructive Positive Qualification Tiers.**  
   Binary "GO / CAUTION / HIGH RISK" traffic lights lead to conversations that stall on risk rather than path forward. The agent replaces them with effort-oriented tiers — *Minimal Effort (Turnkey)*, *Minor Effort*, *Moderate Effort*, *Significant Effort*, *Not Possible As-Is (Alternative Required)* — each accompanied by concrete next steps or drop-in substitutes (e.g., IBM ESSL or OpenBLAS in place of Intel MKL), keeping the sales conversation constructive and solution-oriented.

6. **Universal Multi-Modal Ingestion Including Live URL Crawling.**  
   The normaliser accepts free-form customer emails, formal SBOMs, and direct GitHub or documentation URLs. When a URL is provided (e.g., `https://github.com/facebook/rocksdb`), the agent autonomously crawls the repository manifest files and web documentation, infers all package dependencies and versions via LLM extraction, and feeds them into the same triage pipeline — eliminating the need for customers to provide a structured manifest at all.

---

## 6. Strategic Alignment

This prototype directly accelerates IBM Power infrastructure revenue by eliminating the longest single delay in the enterprise pre-sales cycle. It demonstrates IBM's hybrid AI leadership — combining deterministic knowledge systems with generative reasoning — applied to a mission-critical, real-world enterprise challenge. It protects IBM Power Porting Lab capacity by ensuring senior engineers receive only pre-qualified, fully scoped engineering handoffs rather than spending senior time on routine binary-availability checks. And it positions IBM pre-sales teams as the most technically prepared, fastest-responding team in any competitive platform evaluation.

---

*Submitted for the AI Elite Program Prototype Evaluation.*
