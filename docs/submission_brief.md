# IBM Power Porting Triage Agent — Submission Brief

**AI Elite Program · Autonomous AI Agent Prototype**
**Target:** IBM Power (`ppc64le`) — RHEL 8/9, OpenShift OCP, Ubuntu, SLES

---

## Problem

Every IBM Power pre-sales engagement stalls on one question: *"Will our stack run on Power, and what will porting cost?"* Today this takes **5–10 business days** of manual registry searches and guesswork sizing with **2×–5× variance**. Hidden transitive build deps surface only after porting begins, causing overruns. Porting Lab engineers spend ~40% of their time on routine triage.

---

## Solution

The **Autonomous IBM Power Porting Triage Agent** qualifies a full migration in **< 30 seconds** via a 7-stage pipeline:

1. **Normaliser** — Ingests SBOMs, Dockerfiles, `requirements.txt`, `pom.xml`, emails, or GitHub/docs URLs into canonical purls.
2. **Prober** — Version-aware queries across Docker Hub, Quay.io, RHEL/EPEL, PyPI, Maven, and IBM Open-CE.
3. **Build Scoper** — Recursively extracts `BuildRequires`; checks every transitive dep for ppc64le availability.
4. **Arch Auditor** — Flags x86 SIMD (`AVX2`/AVX-512), inline assembly, and 4KB-page allocators; generates SIMDe/VSX remediations.
5. **CI Scanner** — Detects Power CI markers upstream to modulate effort.
6. **Sizing Engine** — Build + Engineering + Test effort with SIMD multipliers; rounds to next Fibonacci ceiling.
7. **LLM Synthesis** — Gemini 2.5 Flash writes the customer memo; falls back to deterministic KB offline.

**Outputs:** Scorecard · Dependency Matrix · Architecture Audit · Executive PDF · JIRA CSV

---

## Impact

| | Before | After |
|:---|:---|:---|
| Qualification time | 5–10 business days | < 30 seconds |
| Lab triage burden | ~40% of senior time | Zero — scoped specs only |
| Sizing accuracy | 2×–5× variance | Fibonacci ceiling, full audit trail |
| Deliverables | Days of manual prep | 1-click, in-session |

5 enterprise scenarios validated — 8 tests, 100% pass rate.

---

## Key Innovations

1. **Recursive Iceberg Scoping** — Full transitive build graph scoped before work; each node has its own person-day estimate.
2. **4-Tier SIMD Classification** — `DIRECT`→`SIMDE_COMPATIBLE`→`PARTIAL_REWRITE`→`FULL_REDESIGN` (1.0×–4.0×) with volume brackets.
3. **Fibonacci Sizing Ceiling** — One defensible number (e.g., 21 PD) replacing ambiguous ranges.
4. **64KB Page-Size Awareness** — Detects jemalloc-style allocators; prescribes `--with-lg-page=16`.
5. **Constructive Tiers** — *Turnkey → Significant → Alternative Required* with drop-ins (IBM ESSL for Intel MKL).
6. **Live URL Ingestion** — Crawls GitHub repos and docs; no structured manifest required.

---

## Strategic Alignment

Eliminates the longest bottleneck in the IBM Power pre-sales cycle, protects Porting Lab capacity, and proves hybrid AI leadership — deterministic correctness with generative communication.

---

*Submitted for the AI Elite Program Prototype Evaluation.*
