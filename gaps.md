# Gaps Remediation Plan — Estimation & Effort Improvements

## Overview

Seven gaps exist in the current triage estimation logic:

1. **Version-Aware Availability** — The prober ignores the requested version when checking availability. A newer version than what is available on ppc64le should be treated as `UNPORTED_BUILD_REQUIRED`; an older requested version should trigger an upgrade recommendation.
2. **LOC / SIMD Instruction Count Scaling** — Arch complexity effort (`arch_complexity_effort_pd`) is a fixed constant regardless of how many SIMD intrinsic call-sites exist in the source. Gemini LLM should estimate the SIMD instruction count as part of the existing architecture analysis step, and effort should scale with that count.
3. **SIMD-to-VSX Mapping Complexity** — All SIMD porting effort is treated as equal. A four-tier classification (`DIRECT`, `SIMDE_COMPATIBLE`, `PARTIAL_REWRITE`, `FULL_REDESIGN`) with distinct effort multipliers should govern how hard it actually is to port a given package's SIMD code to IBM Power VSX/VMX.
4. **Testing Effort & Test Dependency Availability** — The triage pipeline accounts for build-time dependencies but completely ignores the test phase. Missing test frameworks (e.g. `pytest`, `gtest`, `catch2`), runtime containers needed for integration tests (e.g. a database image, a mock service image), and other test-time dependencies all represent unaccounted effort that can block validation of a ported package on ppc64le.
5. **Dockerfile Base Image Analysis** — When a source repository is available (main package or any unported dependency), all Dockerfiles found anywhere in the repo tree (including CI, test, and sub-directory Dockerfiles) are not currently inspected. Unsupported base images (e.g. `ubuntu:22.04` without a ppc64le manifest, or `FROM scratch` with a baked x86 binary) can silently block containerised workloads.
6. **Source Code Architecture Support Analysis** — The pipeline does not inspect source code to detect existing ppc64le support (e.g. `#ifdef __powerpc64__` guards, `GOARCH=ppc64le` build tags, existing Power CI matrix entries). Presence of such markers is a strong positive signal that significantly reduces effort; their absence is a sizing input. If a `git_repo_url` is provided, a shallow clone and scan should be performed; otherwise Gemini LLM should reason from package metadata.
7. **YAML & Compose File Image Checks** — `docker-compose*.yml`, `.github/workflows/*.yml`, `k8s/*.yaml`, and `helm/values.yaml` files in source repositories may reference Docker images not available on ppc64le. These files are not currently scanned, leaving infrastructure-layer blockers undetected.



---

## Sub-Task 1 — Version-Aware Availability Checking

### Intent
When a specific version is requested, the prober must compare it against what is actually available on ppc64le rather than treating name-only matches as unconditionally available. Two cases must be handled:

- **Requested version is newer than what is available** → status becomes `UNPORTED_BUILD_REQUIRED`; evidence states which version is available and which was requested.
- **Requested version is older than what is available** → status stays as resolved (e.g. `NATIVE_AVAILABLE`) but a warning is added recommending upgrade to the available version.

The `"latest"` sentinel bypasses version comparison entirely.

### Expected Outcomes
- The curated cache lookup in `probe_component` passes version into a comparison helper instead of returning the cached entry unconditionally.
- The live PyPI probe queries the specific version endpoint (`/pypi/{name}/{version}/json`) when a non-latest version is requested, and compares available wheels.
- The Docker Hub probe checks the specific tag rather than defaulting to `latest`.
- The Gemini LLM prompt explicitly includes the requested version and instructs the model to state whether that exact version is available, and if not, which version is.
- `PackageTriageResult` carries a new `version_warning` field to surface the upgrade or unavailability note in the report.

### Relevant Context
- `backend/prober.py` — `probe_component` (line 168), `_probe_pypi` (line 294), `_probe_docker_hub` (line 268), `_probe_gemini_llm` (line 337)
- `backend/models.py` — `PackageTriageResult` (line 70)
- `backend/agent.py` — `_generate_executive_brief` (line 336)
- The curated `POWER_ECOSYSTEM_CACHE` dict in `prober.py` (line 11) does not store a version; version comparison for cache hits must treat the cache entry's available version as the latest known stable.


---

## Sub-Task 2 — SIMD Instruction Count Scaling via Gemini LLM

### Intent
The current `arch_complexity_effort_pd` is a hardcoded constant (e.g. `3.0` for simdjson, `2.0` for heuristic vector packages). This ignores the actual code surface area. A package with 10 SIMD call-sites is far cheaper to port than one with 500.

Gemini LLM already runs a code-analysis prompt for packages with arch friction (in `agent.py`, the `ArchitectureHeuristicAgent` step). That prompt should be extended to also return an estimated SIMD instruction count. The `BuildAnalyzer` will then use this count to scale `arch_complexity_effort_pd` using a tiered formula.

### Expected Outcomes
- `ArchSensitivity` in `models.py` has a new `simd_instruction_count: int` field (default `0`).
- The Gemini architecture analysis prompt in `agent.py` requests an estimated SIMD instruction count and populates `arch_sensitivity.simd_instruction_count`.
- `BuildAnalyzer` applies a scaling formula to `arch_complexity_effort_pd` based on instruction count:
  - `0` (no SIMD) → no scaling, existing base effort applies
  - `1–50` → `×1.0` (small, current baseline)
  - `51–200` → `×1.5` (moderate surface)
  - `201–500` → `×2.5` (large surface)
  - `> 500` → `×4.0` (extensive, likely core algorithm)
- `confidence_level` is set to `"Estimated"` when the count comes from LLM inference (not a curated KB entry).

### Relevant Context
- `backend/models.py` — `ArchSensitivity` (line 39)
- `backend/agent.py` — Gemini architecture analysis block (lines 213–238)
- `backend/build_analyzer.py` — `analyze_package_build` (line 73), `_dynamic_heuristic_build` (line 137)

### Status
[ ] pending

---

## Sub-Task 3 — SIMD-to-VSX Porting Complexity Classification

### Intent
Not all SIMD intrinsics are equally hard to port to IBM Power VSX/VMX. The current code applies the same effort regardless of whether an intrinsic has a direct VSX equivalent or requires a full algorithmic redesign. A four-tier enum drives distinct effort multipliers and distinct remediation guidance:

| Tier | Meaning | Effort Multiplier |
|---|---|---|
| `DIRECT` | 1:1 VSX semantic match exists (e.g. `_mm_add_epi32` → `vec_add`). Drop-in SIMDe header sufficient. | ×1.0 |
| `SIMDE_COMPATIBLE` | SIMDe library covers the intrinsic set used. Minor header inclusion + recompile. | ×1.5 |
| `PARTIAL_REWRITE` | Partial VSX match; register width or lane-count differs. Loops or data layout must be restructured. | ×2.5 |
| `FULL_REDESIGN` | No VSX semantic equivalent (e.g. `_mm512_conflict_epi32`, AES-NI, SHA-NI). Algorithm must be rewritten from scratch or replaced with a scalar path. | ×4.0 |

Gemini LLM (already invoked for arch analysis) classifies the tier based on the intrinsic set detected in the code snippet.

### Expected Outcomes
- A new `SIMDPortingComplexity` enum (`DIRECT`, `SIMDE_COMPATIBLE`, `PARTIAL_REWRITE`, `FULL_REDESIGN`) is added to `models.py`.
- `ArchSensitivity` has a new `simd_porting_complexity: SIMDPortingComplexity` field (default `DIRECT`).
- The Gemini architecture prompt in `agent.py` asks for the complexity tier and populates `pkg.arch_sensitivity.simd_porting_complexity`.
- `BuildAnalyzer._scale_arch_effort` (introduced in Sub-Task 2) applies the complexity multiplier on top of the instruction-count multiplier:
  `final_arch_effort = base_arch_effort × count_multiplier × complexity_multiplier`
- The remediation strategy text in `ArchSensitivity` is updated per tier to give specific actionable guidance (e.g. for `SIMDE_COMPATIBLE`: "Add `#include <simde/x86/avx2.h>` and recompile"; for `FULL_REDESIGN`: "Replace with scalar fallback or Power-native algorithm").
- `confidence_level` is `"Estimated"` when classification came from LLM.

### Relevant Context
- `backend/models.py` — `ArchSensitivity` (line 39)
- `backend/agent.py` — Gemini architecture analysis block (lines 213–238)
- `backend/build_analyzer.py` — `KNOWLEDGE_BASE_NATIVE_BUILDS` (line 14), `_dynamic_heuristic_build` (line 137)
- Sub-Task 2 must be completed before this sub-task, as it introduces `_scale_arch_effort`.



---

## Sub-Task 4 — Testing Effort & Test Dependency Availability

### Intent
A porting project is not complete until the workload has been validated by running its test suite on ppc64le. The current pipeline only models build-time and architecture complexity effort — it does not check whether the tools and runtime dependencies needed to *run* tests are themselves available on ppc64le.

Three categories of test dependency must be checked:

1. **Test frameworks** — language-level testing tools used directly by the package's own test suite (e.g. `pytest`, `gtest`, `catch2`, `junit`, `jest`). These are compile-time or install-time requirements specific to exercising the package under test.
2. **Runtime test containers** — Docker/OCI images that must be present and running during integration or end-to-end tests (e.g. a `postgres` container for a database integration test, a `redis` container for a cache layer test, a mock-service image). These are infrastructure-level dependencies that need a ppc64le multi-arch image.
3. **Other test-time native libraries** — system packages or native extensions only pulled in by test targets, not by the main build (e.g. `valgrind`, `lcov`, `gcovr` for coverage, a sanitizer-enabled libc build).

For each of these categories, the prober's existing availability logic (curated cache + live API + Gemini LLM) is re-used. Any test dependency that is `UNPORTED_BUILD_REQUIRED` or `BLOCKER` adds effort to the parent package's total and is flagged separately so it is visible without being conflated with build effort.

### Expected Outcomes
- A new `TestDependency` model is added to `models.py` — similar in shape to `BuildDependency` but with a `test_dep_type` field (`"framework"`, `"runtime_container"`, `"native_lib"`).
- `PackageTriageResult` gains a `test_dependencies: List[TestDependency]` field and a `test_effort_pd: float` field (default `0.0`).
- `TriageSummary` gains a `test_deps_unresolved_count: int` field summarising how many test dependencies across the whole manifest are not yet available on ppc64le.
- A curated test-dependency knowledge base (`TEST_DEPENDENCY_CACHE`) is added to `build_analyzer.py` covering the most common frameworks and runtime containers with their ppc64le availability status:
  - `pytest` → `PLATFORM_AGNOSTIC` (pure Python, 0 PD)
  - `gtest` / `googletest` → `NATIVE_AVAILABLE` (RHEL AppStream ppc64le, 0 PD)
  - `catch2` → `NATIVE_AVAILABLE` (Fedora/EPEL ppc64le, 0 PD)
  - `valgrind` → `NATIVE_AVAILABLE` (natively supports ppc64le, 0 PD)
  - `lcov` / `gcovr` → `NATIVE_AVAILABLE` (0 PD)
  - `postgres` container → `NATIVE_AVAILABLE` (official multi-arch, 0 PD)
  - `redis` container → `NATIVE_AVAILABLE` (official multi-arch, 0 PD)
  - `mysql` container → `NATIVE_AVAILABLE` (Red Hat catalog ppc64le, 0 PD)
  - `mongodb` container → `UNPORTED_BUILD_REQUIRED` (no official ppc64le image, 1 PD)
  - `jest` → `PLATFORM_AGNOSTIC` (pure JS, 0 PD)
- `BuildAnalyzer.analyze_package_build` calls a new `_analyze_test_dependencies(package, target_os)` method that:
  1. Infers likely test frameworks from the package's ecosystem (e.g. `pypi` → check for `pytest`; `native_c` using CMake → check for `gtest`/`catch2`; `npm` → check for `jest`).
  2. For `UNPORTED_BUILD_REQUIRED` packages, uses the Gemini LLM (via an additional prompt) to identify any runtime container images referenced in the package's CI/test configuration and checks their ppc64le availability.
  3. Accumulates `test_effort_pd` from unresolved test dependencies and adds it to `total_effort_pd`.
- The executive brief markdown surfaces a dedicated **"Test Dependency Readiness"** section listing unresolved test dependencies and the additional effort they carry.
- Existing tests in `test_backend.py` are extended: `test_build_analyzer_unported_transitive_deps` is updated to assert `test_dependencies` is populated and `test_effort_pd >= 0`.


### Relevant Context
- `backend/models.py` — `BuildDependency` (line 59), `PackageTriageResult` (line 70), `TriageSummary` (line 95)
- `backend/build_analyzer.py` — `KNOWLEDGE_BASE_NATIVE_BUILDS` (line 14), `analyze_package_build` (line 73)
- `backend/agent.py` — Step 4 aggregation (lines 246–301), `_generate_executive_brief` (line 336), `_generate_csv` (line 419)
- `backend/tests/test_backend.py` — `test_build_analyzer_unported_transitive_deps` (line 85)
- Sub-Task 4 is independent of Sub-Tasks 2 and 3 but should be implemented after Sub-Task 1 so version-aware probing is available for checking test dependency versions.


---

## Sub-Task 6 — Source Code Architecture Support Analysis (Repository Scanner)

### Intent
The `git_repo_url` field already exists on `TriageRequest` but is never used — the agent ignores it entirely. Source code is the most reliable signal for understanding porting effort: the presence of `#ifdef __powerpc64__` guards, `GOARCH=ppc64le` build tags, or existing Power entries in a CI matrix strongly indicates the package already supports ppc64le (reducing effort); their complete absence is a signal that more work is expected.

This sub-task introduces the repository access layer that Sub-Tasks 5 and 7 also rely on:
- If `git_repo_url` is provided, perform a **shallow clone** (`--depth 1`) into a temporary directory and scan source files.
- If no URL is provided, fall back to Gemini LLM reasoning from the package name, version, and ecosystem metadata.

The scan looks for three categories of evidence:
1. **Positive ppc64le support markers** — existing architecture guards, build flags, or CI matrix entries targeting `ppc64le` / `power` / `powerpc`. Each finding lowers the estimated porting effort.
2. **Negative markers** — hard-coded `x86_64`-only paths with no Power counterpart, `__attribute__((target("avx2")))` without fallback, `FAIL_ON_UNSUPPORTED_ARCH` guards. Each finding raises effort or triggers a warning.
3. **Neutral / unknown** — no architecture-specific code found; effort estimate uses existing heuristics.

The scan results are stored in a new `ArchSupportScan` model and surfaced in the executive brief and per-package effort adjustment.

### Expected Outcomes
- A new `ArchSupportScan` model is added to `models.py` with fields: `ppc64le_markers_found: List[str]`, `x86_only_markers_found: List[str]`, `ci_matrix_has_power: bool`, `scan_source: str` (`"repo_clone"` or `"llm_inference"`), `effort_adjustment_factor: float` (1.0 = neutral, < 1.0 = effort reduced, > 1.0 = effort increased).
- `PackageTriageResult` gains an `arch_support_scan: Optional[ArchSupportScan]` field.
- A new `RepoScanner` class is added to a new file `backend/repo_scanner.py` with:
  - `shallow_clone(git_url, tmp_dir)` — runs `git clone --depth 1 --no-tags` into a temp directory; cleans up after use.
  - `scan_arch_support(repo_dir) -> ArchSupportScan` — uses `grep`-style pattern matching across `*.c`, `*.cpp`, `*.h`, `*.go`, `*.rs`, `*.py`, `Makefile`, `CMakeLists.txt` files for the markers listed above. Returns the scan result.
  - `llm_infer_arch_support(package_name, version, ecosystem, gemini_client) -> ArchSupportScan` — prompts Gemini to reason about known ppc64le support for the package.
- `TriageAgent` in `agent.py` calls `RepoScanner` for `UNPORTED_BUILD_REQUIRED` packages when `triage_depth == "deep"`, storing results on `pkg.arch_support_scan`.
- `BuildAnalyzer.analyze_package_build` reads `arch_support_scan.effort_adjustment_factor` and multiplies the computed `total_effort_pd` by it (clamped to the range 0.5–2.0).
- The executive brief includes a "Source Architecture Compatibility" section per unported package, listing found markers and the effort adjustment applied.
- A new test `test_repo_scanner_llm_fallback` in `test_backend.py` verifies that when no URL is provided and no Gemini client is active, `ArchSupportScan` is returned with `scan_source="llm_inference"` and sensible defaults.


### Relevant Context
- `backend/models.py` — `ArchSensitivity` (line 39), `PackageTriageResult` (line 70)
- `backend/agent.py` — `BuildScopingAgent` deep-scan loop (lines 176–239), `TriageRequest.git_repo_url` (line 129)
- `backend/build_analyzer.py` — `analyze_package_build` (line 73)
- `backend/tests/test_backend.py` — existing test structure



---

## Sub-Task 5 — Dockerfile Base Image Analysis in Repository

### Intent
Source repositories commonly contain multiple Dockerfiles — in the project root, under `docker/`, `ci/`, `test/`, or `.devcontainer/`. Each `FROM <image>:<tag>` line is a potential ppc64le blocker if the image has no multi-arch manifest for `linux/ppc64le`.

The existing `MultiSourceProber` already knows how to check Docker Hub and Quay.io for ppc64le manifests. This sub-task wires repository Dockerfile discovery to that existing probe, so every base image found in every Dockerfile in the repo is checked and any unsupported ones are flagged with effort.

Special cases:
- `FROM scratch` — always a blocker if it is followed by a `COPY` of a pre-built binary (Gemini LLM classifies whether the copied binary is x86-only).
- Multi-stage builds — each stage's `FROM` is checked independently.
- `ARG`-parametrised base images (e.g. `ARG BASE=ubuntu:22.04 \n FROM $BASE`) — the default value is extracted and checked.

### Expected Outcomes
- A new `DockerfileImageFinding` model is added to `models.py` with fields: `dockerfile_path: str`, `base_image: str`, `tag: str`, `stage_name: Optional[str]`, `status: AvailabilityStatus`, `notes: Optional[str]`, `effort_pd: float`.
- `PackageTriageResult` gains a `dockerfile_image_findings: List[DockerfileImageFinding]` field.
- `RepoScanner` (introduced in Sub-Task 6) gains a `scan_dockerfiles(repo_dir) -> List[Tuple[str, List[str]]]` method that:
  1. Walks the repo tree for files named `Dockerfile`, `Dockerfile.*`, or `*.dockerfile`.
  2. Extracts all `FROM` lines (resolving `ARG` defaults where possible).
  3. Returns a list of `(dockerfile_path, [base_image_refs])` tuples.
- `TriageAgent` calls `scan_dockerfiles` then feeds each base image through the existing `MultiSourceProber.probe_component` (ecosystem `"container"`) and creates `DockerfileImageFinding` entries.
- Any finding with status `UNPORTED_BUILD_REQUIRED` or `BLOCKER` adds `0.5 PD` per unsupported image to the package's `total_effort_pd` (re-base image, not a full port — effort is for switching the base image).
- The executive brief includes a "Dockerfile Base Image Audit" section per package, listing each Dockerfile path, each base image, and its ppc64le status.
- A new test `test_dockerfile_image_scan` in `test_backend.py` verifies that a mock repo directory with a synthetic Dockerfile containing a known-unsupported image produces the expected `DockerfileImageFinding`.



### Relevant Context
- `backend/repo_scanner.py` — introduced in Sub-Task 6
- `backend/prober.py` — `MultiSourceProber.probe_component` (line 168), `_probe_docker_hub` (line 268), `_probe_quay` (line 237)
- `backend/models.py` — `AvailabilityStatus` (line 25), `PackageTriageResult` (line 70)
- `backend/agent.py` — deep-scan loop (lines 176–239), `_generate_executive_brief` (line 336)
- **Depends on Sub-Task 6** for `RepoScanner` and `scan_dockerfiles`.


---

## Sub-Task 7 — YAML & Compose File Image Checks

### Intent
`docker-compose*.yml`, `.github/workflows/*.yml`, `k8s/*.yaml`, and `helm/values.yaml` files in a source repository often reference Docker images used for local development, CI, or Kubernetes deployment. These are distinct from Dockerfiles (which define how to *build* an image) — these files reference pre-built images that are *pulled* at runtime or in CI. If those images have no ppc64le manifest, the entire CI pipeline or deployment will fail on Power, even if the application itself has been successfully ported.

The check re-uses `MultiSourceProber` for availability, the same way Sub-Task 5 does for Dockerfile base images.

### Expected Outcomes
- A new `ConfigImageFinding` model is added to `models.py` with fields: `config_file_path: str`, `config_file_type: str` (`"compose"`, `"github_workflow"`, `"k8s_manifest"`, `"helm_values"`), `image_ref: str`, `status: AvailabilityStatus`, `notes: Optional[str]`, `effort_pd: float`.
- `PackageTriageResult` gains a `config_image_findings: List[ConfigImageFinding]` field.
- `RepoScanner` (Sub-Task 6) gains a `scan_config_images(repo_dir) -> List[Tuple[str, str, List[str]]]` method that:
  1. Finds files matching the well-known patterns: `docker-compose*.yml`, `.github/workflows/*.yml`, `k8s/*.yaml`, `helm/values.yaml`.
  2. Parses each file and extracts image references: `image:` keys in Compose/K8s YAML, `uses:` Docker container actions in GitHub workflow files, `repository:` / `tag:` in Helm values.
  3. Returns a list of `(file_path, file_type, [image_refs])` tuples.
- `TriageAgent` calls `scan_config_images` then probes each image ref through `MultiSourceProber` and creates `ConfigImageFinding` entries.
- Any `UNPORTED_BUILD_REQUIRED` or `BLOCKER` image finding adds `0.5 PD` per image to the package's total effort (cost to replace or rebuild the image for ppc64le).
- The executive brief includes a "CI/Deployment Config Image Audit" section listing flagged images per file.
- A new test `test_config_image_scan` in `test_backend.py` verifies that a mock repo directory with a synthetic `docker-compose.yml` referencing a known-unsupported image produces the expected `ConfigImageFinding`.


### Relevant Context
- `backend/repo_scanner.py` — introduced in Sub-Task 6
- `backend/prober.py` — `MultiSourceProber.probe_component` (line 168)
- `backend/models.py` — `PackageTriageResult` (line 70)
- `backend/agent.py` — deep-scan loop (lines 176–239), `_generate_executive_brief` (line 336)
- **Depends on Sub-Task 6** for `RepoScanner` and `scan_config_images`.

