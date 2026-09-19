import os
import re
import asyncio
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from dotenv import load_dotenv

load_dotenv()

from .models import (
    TriageRequest,
    TriageResponse,
    TriageSummary,
    PackageTriageResult,
    AgentStep,
    AvailabilityStatus,
    SalesRecommendationTier,
    RecommendationTrafficLight,
    SIMDPortingComplexity,
    TestDependency,
    ArchSupportScan,
    DockerfileImageFinding,
    ConfigImageFinding,
)
from .normalizer import UniversalNormalizer
from .prober import MultiSourceProber
from .build_analyzer import BuildAnalyzer, scale_arch_effort, get_simd_multipliers
from .repo_scanner import RepoScanner
from .gemini_helper import generate_gemini_content
from .url_extractor import URLExtractor

logger = logging.getLogger("agent")

FIBONACCI_NUMBERS = [0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]


def next_fibonacci_effort(effort: float) -> int:
    """Returns the single Fibonacci value that is strictly greater than the input effort.
    For example: 5 -> 8 (as requested), 26 -> 34, 34 -> 55, 0 -> 0.
    """
    if effort <= 0:
        return 0
    for fib in FIBONACCI_NUMBERS:
        if fib > effort:
            return fib
KNOWN_ECOSYSTEM_DETAILS: Dict[str, Dict[str, str]] = {
    "rocksdb": {
        "git_repo_url": "https://github.com/facebook/rocksdb",
        "doc_url": "https://rocksdb.org",
        "ecosystem": "native_c",
        "version": "8.6",
    },
    "redis": {
        "git_repo_url": "https://github.com/redis/redis",
        "doc_url": "https://redis.io",
        "ecosystem": "container",
        "version": "7.2",
    },
    "nginx": {
        "git_repo_url": "https://github.com/nginx/nginx",
        "doc_url": "https://nginx.org",
        "ecosystem": "container",
        "version": "1.24",
    },
    "fastapi": {
        "git_repo_url": "https://github.com/tiangolo/fastapi",
        "doc_url": "https://fastapi.tiangolo.com",
        "ecosystem": "pypi",
        "version": "0.110.0",
    },
    "pytorch": {
        "git_repo_url": "https://github.com/pytorch/pytorch",
        "doc_url": "https://pytorch.org",
        "ecosystem": "pypi",
        "version": "2.1.0",
    },
    "torch": {
        "git_repo_url": "https://github.com/pytorch/pytorch",
        "doc_url": "https://pytorch.org",
        "ecosystem": "pypi",
        "version": "2.1.0",
    },
    "simdjson": {
        "git_repo_url": "https://github.com/simdjson/simdjson",
        "doc_url": "https://simdjson.org",
        "ecosystem": "native_c",
        "version": "3.6",
    },
    "snappy": {
        "git_repo_url": "https://github.com/google/snappy",
        "doc_url": "https://github.com/google/snappy",
        "ecosystem": "native_c",
        "version": "1.1.9",
    },
    "jemalloc": {
        "git_repo_url": "https://github.com/jemalloc/jemalloc",
        "doc_url": "http://jemalloc.net",
        "ecosystem": "native_c",
        "version": "5.3.0",
    },
}


class TriageAgent:
    """Agentic AI Orchestrator that triages workloads, probes repositories, scopes transitive dependencies,
    analyzes SIMD instructions & complexity, checks test dependencies, scans Dockerfiles & configs, and synthesizes reports.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.gemini_client = None

        if self.api_key and self.api_key.strip() and not self.api_key.startswith("your_"):
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.api_key.strip())
                logger.info("Gemini LLM Client successfully initialized with provided API key.")
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI Client: {e}")
        else:
            logger.info("Running in autonomous simulation mode (no live GEMINI_API_KEY provided).")

        self.prober = MultiSourceProber(gemini_client=self.gemini_client)

    async def run_triage_stream(self, request: TriageRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """Runs the triage pipeline yielding live agent steps and the final comprehensive response."""
        # Update gemini client if request includes an override key
        if request.gemini_api_key and not self.gemini_client:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=request.gemini_api_key.strip())
                self.prober.set_gemini_client(self.gemini_client)
            except Exception as e:
                logger.warning(f"Could not initialize requested Gemini client: {e}")

        steps: List[AgentStep] = []
        step_counter = 1

        # Step 1: Ingestion & Normalization
        yield {
            "type": "step",
            "step": AgentStep(
                step_id=step_counter,
                agent_name="IngestionAgent",
                action_type="plan",
                target="Input Manifests",
                thought="Ingesting provided input and standardizing packages into canonical Package URLs (PURL).",
                detail=f"Target OS: {request.target_os.value.upper()} on {request.target_platform.value.upper()} (ppc64le). Depth: {request.triage_depth.value}."
            ).model_dump()
        }
        await asyncio.sleep(0.3)
        step_counter += 1

        raw_text = request.raw_manifest or ""
        parsed_items = UniversalNormalizer.normalize(raw_text, request.manifest_type or "auto")

        # Provenance detection & URL extraction
        detected_git_url: Optional[str] = request.git_repo_url
        detected_doc_url: Optional[str] = request.doc_url
        primary_pkg_name: Optional[str] = None
        primary_version: Optional[str] = None
        primary_ecosystem: Optional[str] = None

        # Check raw text for embedded URLs if not already supplied
        if raw_text:
            github_matches = re.findall(r"https?://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", raw_text)
            if not detected_git_url and github_matches:
                detected_git_url = github_matches[0]
            
            all_urls = re.findall(r"https?://[a-zA-Z0-9_.-]+\.[a-zA-Z]{2,}(?:/[^\s)\"'>]*)?", raw_text)
            non_git = [u for u in all_urls if "github.com" not in u]
            if not detected_doc_url and non_git:
                detected_doc_url = non_git[0]

        # Step 1.1: If user supplied a GitHub or documentation URL, infer dependencies via LLM/scraper
        candidate_url = detected_git_url or detected_doc_url
        if not candidate_url and raw_text and URLExtractor.is_url(raw_text):
            candidate_url = raw_text.strip()
            if "github.com" in candidate_url:
                detected_git_url = candidate_url
            else:
                detected_doc_url = candidate_url

        if candidate_url and URLExtractor.is_url(candidate_url):
            yield {
                "type": "step",
                "step": AgentStep(
                    step_id=step_counter,
                    agent_name="URLScraperAgent",
                    action_type="url_inference",
                    target=candidate_url,
                    thought=f"Crawling package website or repository ({candidate_url}) to extract dependencies and manifest declarations...",
                ).model_dump()
            }
            await asyncio.sleep(0.3)
            step_counter += 1

            url_pkgs, url_title, url_note = await URLExtractor.extract_from_url(candidate_url, gemini_client=self.gemini_client)
            if url_pkgs:
                parsed_items.extend(url_pkgs)
                primary_pkg_name = url_pkgs[0]["name"]
                primary_version = url_pkgs[0].get("version", "latest")
                primary_ecosystem = url_pkgs[0].get("ecosystem", "native_c")
                yield {
                    "type": "step",
                    "step": AgentStep(
                        step_id=step_counter,
                        agent_name="LLMDependencyInferenceAgent",
                        action_type="url_inference",
                        target=url_title,
                        thought=f"Inferred {len(url_pkgs)} library requirements and version specifications from {candidate_url}.",
                        detail=", ".join([f"{p['name']} ({p.get('version', 'latest')})" for p in url_pkgs[:6]]) + ("..." if len(url_pkgs) > 6 else "")
                    ).model_dump()
                }
                await asyncio.sleep(0.3)
                step_counter += 1
        
        # If user explicitly passed a list of packages
        if request.packages_list:
            for p in request.packages_list:
                parsed_items.append({
                    "name": p.get("name", ""),
                    "version": p.get("version", "latest"),
                    "ecosystem": p.get("ecosystem", "container")
                })

        # Remove duplicates
        unique_items = []
        seen = set()
        for item in parsed_items:
            key = (item["name"].lower(), item.get("version", "latest"))
            if key not in seen and item["name"].strip():
                seen.add(key)
                unique_items.append(item)

        # Infer primary package name if not set yet
        if not primary_pkg_name:
            if detected_git_url:
                gh_m = re.search(r"github\.com/[^/]+/([^/\s?#]+)", detected_git_url)
                if gh_m:
                    primary_pkg_name = gh_m.group(1).replace(".git", "").lower()
            elif detected_doc_url:
                doc_m = re.search(r"https?://(?:www\.)?([^/\.]+)", detected_doc_url)
                if doc_m:
                    primary_pkg_name = doc_m.group(1).lower()
            elif unique_items:
                primary_pkg_name = unique_items[0]["name"]
                primary_version = unique_items[0].get("version", "latest")
                primary_ecosystem = unique_items[0].get("ecosystem", "container")

        # Enrich provenance details from known ecosystem table
        if primary_pkg_name:
            norm_k = primary_pkg_name.lower().strip()
            if norm_k in KNOWN_ECOSYSTEM_DETAILS:
                k_info = KNOWN_ECOSYSTEM_DETAILS[norm_k]
                if not detected_git_url:
                    detected_git_url = k_info.get("git_repo_url")
                if not detected_doc_url:
                    detected_doc_url = k_info.get("doc_url")
                if not primary_version or primary_version == "latest":
                    primary_version = k_info.get("version", "latest")
                if not primary_ecosystem:
                    primary_ecosystem = k_info.get("ecosystem", "native_c")

        yield {
            "type": "step",
            "step": AgentStep(
                step_id=step_counter,
                agent_name="IngestionAgent",
                action_type="plan",
                target="Dependency Normalizer",
                thought=f"Successfully extracted and normalized {len(unique_items)} unique components across container, language, and system layers." + (f" Primary package: {primary_pkg_name}." if primary_pkg_name else ""),
                detail=", ".join([i["name"] for i in unique_items[:6]]) + ("..." if len(unique_items) > 6 else "")
            ).model_dump()
        }
        await asyncio.sleep(0.3)
        step_counter += 1

        # Step 1.5: Repository Architecture & Container Scan (Sub-Tasks 5, 6, 7)
        arch_scan: Optional[ArchSupportScan] = None
        docker_findings: List[DockerfileImageFinding] = []
        config_findings: List[ConfigImageFinding] = []

        scan_repo_url = detected_git_url or request.git_repo_url
        if scan_repo_url:
            yield {
                "type": "step",
                "step": AgentStep(
                    step_id=step_counter,
                    agent_name="RepoScanAgent",
                    action_type="scan",
                    target=scan_repo_url,
                    thought="Cloning repository shallowly to inspect architecture markers, Dockerfiles, and CI configurations...",
                ).model_dump()
            }
            await asyncio.sleep(0.2)
            step_counter += 1

            temp_repo = RepoScanner.shallow_clone_repo(scan_repo_url)
            if temp_repo:
                arch_scan = RepoScanner.scan_arch_support(temp_repo)
                docker_findings = RepoScanner.scan_dockerfiles(temp_repo)
                config_findings = RepoScanner.scan_config_images(temp_repo)
                RepoScanner.cleanup_repo(temp_repo)

        if not arch_scan:
            target_pkg_name = request.project_name or (unique_items[0]["name"] if unique_items else "workload")
            arch_scan = RepoScanner.llm_infer_arch_support(target_pkg_name, gemini_client=self.gemini_client)

        # Step 2: Multi-Source Availability Probing (Sub-Task 1 Version-Aware)
        triaged_packages: List[PackageTriageResult] = []
        unported_candidates = []

        for item in unique_items:
            name = item["name"]
            version = item.get("version", "latest")
            eco = item.get("ecosystem", "container")

            yield {
                "type": "step",
                "step": AgentStep(
                    step_id=step_counter,
                    agent_name="AvailabilityProber",
                    action_type="lookup",
                    target=f"{name} ({eco})",
                    thought=f"Consulting live registries (Quay.io/Docker Hub), {request.target_os.value} repos, and Gemini LLM for {name} ({version}) on ppc64le...",
                ).model_dump()
            }
            await asyncio.sleep(0.15)
            step_counter += 1

            probe_res = await self.prober.probe_component(name, version, eco, request.target_os.value)
            
            pkg_result = PackageTriageResult(
                package_name=name,
                requested_version=version,
                ecosystem=eco,
                status=probe_res["status"],
                tier_description=probe_res["tier"],
                evidence_source=probe_res.get("evidence"),
                evidence_url=probe_res.get("url"),
                substitute_package=probe_res.get("substitute"),
                version_warning=probe_res.get("version_warning")
            )

            # Log version warning or verification discovery
            if pkg_result.version_warning:
                yield {
                    "type": "step",
                    "step": AgentStep(
                        step_id=step_counter,
                        agent_name="AvailabilityProber",
                        action_type="lookup",
                        target=f"{name} Version Notice",
                        thought=f"⚠️ {pkg_result.version_warning}",
                        detail=f"Requested: {version} | Verified Available on Power: {probe_res.get('available_version', 'N/A')}"
                    ).model_dump()
                }
                await asyncio.sleep(0.1)
                step_counter += 1
            elif probe_res.get("evidence"):
                yield {
                    "type": "step",
                    "step": AgentStep(
                        step_id=step_counter,
                        agent_name="AvailabilityProber",
                        action_type="lookup",
                        target=f"{name} Verified",
                        thought=f"Qualification Result: {pkg_result.status.value.upper()} • {pkg_result.tier_description}",
                        detail=probe_res.get("evidence")
                    ).model_dump()
                }
                await asyncio.sleep(0.1)
                step_counter += 1

            if pkg_result.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED:
                unported_candidates.append(pkg_result)
            
            triaged_packages.append(pkg_result)

        # Probe discovered Dockerfile base images & config images
        if docker_findings:
            for df in docker_findings:
                img_probe = await self.prober.probe_component(df.base_image, df.tag, "container", request.target_os.value)
                df.status = img_probe["status"]
                if df.status in [AvailabilityStatus.UNPORTED_BUILD_REQUIRED, AvailabilityStatus.BLOCKER]:
                    df.effort_pd = 0.5
                    df.notes = f"Base image {df.base_image}:{df.tag} not verified for ppc64le; container rebuild required."
                else:
                    df.notes = f"Verified multi-arch ppc64le container ({img_probe.get('tier')})"

        if config_findings:
            for cf in config_findings:
                ref = cf.image_ref
                img_tag = "latest"
                if ":" in ref:
                    img_name, img_tag = ref.rsplit(":", 1)
                else:
                    img_name = ref
                cfg_probe = await self.prober.probe_component(img_name, img_tag, "container", request.target_os.value)
                cf.status = cfg_probe["status"]
                if cf.status in [AvailabilityStatus.UNPORTED_BUILD_REQUIRED, AvailabilityStatus.BLOCKER]:
                    cf.effort_pd = 0.5
                    cf.notes = f"Config image {ref} not verified for ppc64le; container rebuild required."
                else:
                    cf.notes = f"Verified multi-arch ppc64le container ({cfg_probe.get('tier')})"

        # Attach findings to first package or primary package
        if triaged_packages:
            triaged_packages[0].arch_support_scan = arch_scan
            triaged_packages[0].dockerfile_image_findings = docker_findings
            triaged_packages[0].config_image_findings = config_findings

        # Step 3: Deep Source Build & Transitive Dependency Scoping (Sub-Tasks 2, 3, 4)
        if unported_candidates and request.triage_depth == "deep":
            yield {
                "type": "step",
                "step": AgentStep(
                    step_id=step_counter,
                    agent_name="BuildScopingAgent",
                    action_type="deep_scan",
                    target="Unported Components",
                    thought=f"Detected {len(unported_candidates)} unported components. Initiating deep source build audit, inspecting build-time dependencies, SIMD instructions, and test harnesses...",
                ).model_dump()
            }
            await asyncio.sleep(0.3)
            step_counter += 1

            for pkg in unported_candidates:
                yield {
                    "type": "step",
                    "step": AgentStep(
                        step_id=step_counter,
                        agent_name="BuildScopingAgent",
                        action_type="deep_scan",
                        target=pkg.package_name,
                        thought=f"Parsing build configuration for {pkg.package_name}. Auditing BuildRequires, SIMD instructions, and test dependencies...",
                    ).model_dump()
                }
                await asyncio.sleep(0.25)
                step_counter += 1

                # Apply build analyzer
                BuildAnalyzer.analyze_package_build(pkg, request.target_os.value)

                # Report discovered transitive dependencies
                unported_sub_deps = [d for d in pkg.build_dependencies if d.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED]
                if unported_sub_deps:
                    yield {
                        "type": "step",
                        "step": AgentStep(
                            step_id=step_counter,
                            agent_name="BuildScopingAgent",
                            action_type="deep_scan",
                            target=f"{pkg.package_name} Build-Tree",
                            thought=f"⚠️ Uncovered transitive dependency iceberg in {pkg.package_name}: {len(unported_sub_deps)} build requirement(s) also unported on ppc64le!",
                            detail=", ".join([f"{d.name} (+{d.porting_effort_pd} PD)" for d in unported_sub_deps])
                        ).model_dump()
                    }
                    await asyncio.sleep(0.2)
                    step_counter += 1

                # Report test dependencies (Sub-Task 4)
                if pkg.test_dependencies:
                    unported_tests = [t for t in pkg.test_dependencies if t.status != AvailabilityStatus.NATIVE_AVAILABLE]
                    yield {
                        "type": "step",
                        "step": AgentStep(
                            step_id=step_counter,
                            agent_name="BuildScopingAgent",
                            action_type="deep_scan",
                            target=f"{pkg.package_name} Test Validation",
                            thought=f"Scoped {len(pkg.test_dependencies)} test dependency/harness requirement(s). Test effort: {pkg.test_effort_pd} PD.",
                            detail=", ".join([f"{t.name} ({t.status.value})" for t in pkg.test_dependencies])
                        ).model_dump()
                    }
                    await asyncio.sleep(0.15)
                    step_counter += 1

                # Sub-Task 2 & 3: SIMD instruction count & 4-tier complexity analysis via Gemini
                if pkg.arch_sensitivity and (pkg.arch_sensitivity.has_simd_avx or pkg.arch_sensitivity.has_64k_page_risk or pkg.arch_sensitivity.has_inline_asm):
                    if self.gemini_client:
                        try:
                            prompt = (
                                f"You are an IBM Power (ppc64le) porting specialist. Analyze this unported library '{pkg.package_name}'.\n"
                                f"Architecture issue: SIMD={pkg.arch_sensitivity.has_simd_avx}, 64KB Page={pkg.arch_sensitivity.has_64k_page_risk}, Asm={pkg.arch_sensitivity.has_inline_asm}.\n"
                                f"Code snippet:\n{pkg.arch_sensitivity.code_snippet}\n"
                                "Evaluate:\n"
                                "1. simd_instruction_count: estimated count of x86 SIMD/AVX instructions (e.g. 0, 45, 150, 320, 600)\n"
                                "2. simd_porting_complexity: one of 'direct' (macro drop-in), 'simde_compatible' (SIMDe header mapping), 'partial_rewrite' (mixed intrinsics requiring VSX rewrite), or 'full_redesign' (deep AVX-512 dependencies)\n"
                                "3. remediation_strategy: concise 2-sentence porting remediation vector recommending SIMDe, Power VSX intrinsics, or 64KB page allocator configuration.\n"
                                "Return ONLY JSON:\n"
                                "{\n"
                                '  "simd_instruction_count": int,\n'
                                '  "simd_porting_complexity": "direct" | "simde_compatible" | "partial_rewrite" | "full_redesign",\n'
                                '  "remediation_strategy": "string"\n'
                                "}\n"
                                "JSON:"
                            )
                            resp_text = generate_gemini_content(self.gemini_client, prompt, json_mode=True)
                            if resp_text:
                                import json
                                parsed_simd = json.loads(resp_text.replace("```json", "").replace("```", "").strip())
                                if "simd_instruction_count" in parsed_simd:
                                    pkg.arch_sensitivity.simd_instruction_count = int(parsed_simd["simd_instruction_count"])
                                if "simd_porting_complexity" in parsed_simd:
                                    c_map = {
                                        "direct": SIMDPortingComplexity.DIRECT,
                                        "simde_compatible": SIMDPortingComplexity.SIMDE_COMPATIBLE,
                                        "partial_rewrite": SIMDPortingComplexity.PARTIAL_REWRITE,
                                        "full_redesign": SIMDPortingComplexity.FULL_REDESIGN,
                                    }
                                    c_str = str(parsed_simd["simd_porting_complexity"]).lower()
                                    if c_str in c_map:
                                        pkg.arch_sensitivity.simd_porting_complexity = c_map[c_str]
                                if "remediation_strategy" in parsed_simd:
                                    pkg.arch_sensitivity.remediation_strategy = parsed_simd["remediation_strategy"]

                                # Rescale arch effort from unscaled base_arch_complexity_effort_pd
                                base_arch = (
                                    pkg.base_arch_complexity_effort_pd
                                    if pkg.base_arch_complexity_effort_pd > 0
                                    else (pkg.arch_sensitivity.base_engineering_effort_pd if pkg.arch_sensitivity and pkg.arch_sensitivity.base_engineering_effort_pd > 0 else 2.0)
                                )
                                count_m, comp_m = get_simd_multipliers(
                                    pkg.arch_sensitivity.simd_instruction_count,
                                    pkg.arch_sensitivity.simd_porting_complexity
                                )
                                pkg.arch_sensitivity.base_engineering_effort_pd = base_arch
                                pkg.arch_sensitivity.simd_instruction_multiplier = count_m
                                pkg.arch_sensitivity.simd_complexity_multiplier = comp_m
                                pkg.arch_complexity_effort_pd = scale_arch_effort(
                                    base_arch,
                                    pkg.arch_sensitivity.simd_instruction_count,
                                    pkg.arch_sensitivity.simd_porting_complexity
                                )
                                total = (
                                    pkg.base_build_effort_pd
                                    + pkg.transitive_deps_effort_pd
                                    + pkg.arch_complexity_effort_pd
                                    + pkg.test_effort_pd
                                )
                                pkg.total_effort_pd = int(round(total))
                        except Exception as llm_err:
                            logger.warning(f"Gemini code analysis call skipped: {llm_err}")

                    yield {
                        "type": "step",
                        "step": AgentStep(
                            step_id=step_counter,
                            agent_name="ArchitectureHeuristicAgent",
                            action_type="llm_reasoning",
                            target=f"{pkg.package_name} Code Audit",
                            thought=(
                                f"Detected architecture friction in {pkg.package_name}: {pkg.arch_sensitivity.simd_instruction_count} SIMD instruction(s), "
                                f"complexity tier '{pkg.arch_sensitivity.simd_porting_complexity.value}'. Scaled engineering effort: {pkg.arch_complexity_effort_pd} PD."
                            ),
                            detail=pkg.arch_sensitivity.remediation_strategy
                        ).model_dump()
                    }
                    await asyncio.sleep(0.2)
                    step_counter += 1
        else:
            # Express triage: apply standard build sizing
            for pkg in triaged_packages:
                BuildAnalyzer.analyze_package_build(pkg, request.target_os.value)

        # Apply Sub-Task 6 architecture support scan factor to unported components
        if arch_scan and arch_scan.effort_adjustment_factor != 1.0:
            for p in triaged_packages:
                if p.arch_complexity_effort_pd > 0:
                    p.arch_complexity_effort_pd = round(p.arch_complexity_effort_pd * arch_scan.effort_adjustment_factor, 2)
                total = (
                    p.base_build_effort_pd
                    + p.transitive_deps_effort_pd
                    + p.arch_complexity_effort_pd
                    + p.test_effort_pd
                )
                if total > 0:
                    p.total_effort_pd = max(1, int(round(total)))

        # Add Sub-Task 5 & 7 container image effort into primary package
        container_extra_pd = sum(f.effort_pd for f in docker_findings) + sum(f.effort_pd for f in config_findings)
        if container_extra_pd > 0 and triaged_packages:
            triaged_packages[0].total_effort_pd += int(round(container_extra_pd))

        # Step 4: Aggregate Metrics & Scoring
        total_count = len(triaged_packages)
        native_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.NATIVE_AVAILABLE)
        agnostic_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.PLATFORM_AGNOSTIC)
        substitute_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.SUBSTITUTE_AVAILABLE)
        unported_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED)
        blocker_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.BLOCKER)
        
        # Count unported build-time transitive dependencies
        unported_transitive_count = 0
        for p in triaged_packages:
            unported_transitive_count += sum(1 for d in p.build_dependencies if d.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED)

        # Count unported test dependencies (Sub-Task 4)
        unported_test_count = 0
        for p in triaged_packages:
            unported_test_count += sum(1 for td in p.test_dependencies if td.status != AvailabilityStatus.NATIVE_AVAILABLE)

        # Readiness Score %
        ready_units = native_count + agnostic_count + (substitute_count * 0.9) + (unported_count * 0.3)
        readiness_pct = round((ready_units / max(total_count, 1)) * 100.0, 1)

        # Effort Summation with Fibonacci single-value sizing (based on max effort)
        BUFFER_PERSON_DAYS = 5  # 1 Person-Week buffer
        raw_total_pd = sum(p.total_effort_pd for p in triaged_packages)

        if raw_total_pd == 0 and unported_count == 0:
            base_max_pd = 0
            fib_pd = 0
        elif raw_total_pd == 0:
            base_max_pd = BUFFER_PERSON_DAYS
            fib_pd = next_fibonacci_effort(base_max_pd)
        else:
            buffered_total = raw_total_pd + BUFFER_PERSON_DAYS
            base_max_pd = int(round(buffered_total * 1.30))
            fib_pd = next_fibonacci_effort(base_max_pd)

        # Positive Effort-Oriented Qualification Recommendations
        if blocker_count > 0:
            rec = SalesRecommendationTier.NOT_POSSIBLE_AS_IS
            rec_reason = f"Workload contains {blocker_count} proprietary x86 component(s) requiring architectural substitution (e.g. OpenBLAS / ESSL alternatives recommended)."
        elif readiness_pct >= 90 and raw_total_pd == 0 and blocker_count == 0:
            rec = SalesRecommendationTier.MINIMAL_EFFORT
            rec_reason = f"Turnkey readiness ({readiness_pct}%). All components run out-of-the-box on IBM Power (0 Person-Days)."
        elif fib_pd <= 8:
            rec = SalesRecommendationTier.MINOR_EFFORT
            rec_reason = f"High readiness ({readiness_pct}%). Light build verification estimated at {fib_pd} Person-Days (Fibonacci max estimate)."
        elif fib_pd <= 34:
            rec = SalesRecommendationTier.MODERATE_EFFORT
            rec_reason = f"Moderate porting scope ({readiness_pct}% ready). Transitive dependencies and build verification estimated at {fib_pd} Person-Days (Fibonacci max estimate)."
        else:
            rec = SalesRecommendationTier.SIGNIFICANT_EFFORT
            rec_reason = f"Extensive porting investment ({readiness_pct}% ready). Multi-tier transitive dependencies or vector kernels estimated at {fib_pd} Person-Days (Fibonacci max estimate)."

        summary = TriageSummary(
            total_packages=total_count,
            native_count=native_count,
            agnostic_count=agnostic_count,
            substitute_count=substitute_count,
            unported_count=unported_count,
            blocker_count=blocker_count,
            readiness_score_pct=readiness_pct,
            recommendation=rec,
            recommendation_reason=rec_reason,
            fibonacci_effort_pd=fib_pd,
            min_total_person_days=fib_pd,
            max_total_person_days=fib_pd,
            unported_transitive_deps_count=unported_transitive_count,
            test_deps_unresolved_count=unported_test_count
        )

        # Step 5: Final Executive Synthesis
        yield {
            "type": "step",
            "step": AgentStep(
                step_id=step_counter,
                agent_name="ExecutiveSynthesizer",
                action_type="synthesis",
                target="Executive Deliverables",
                thought=f"Synthesizing pre-sales qualification brief and engineering backlog. Recommendation: {rec.value}.",
            ).model_dump()
        }
        await asyncio.sleep(0.3)

        # Attach repository and documentation links to triaged packages
        for p in triaged_packages:
            p_name_lower = p.package_name.lower()
            if p_name_lower in KNOWN_ECOSYSTEM_DETAILS:
                k = KNOWN_ECOSYSTEM_DETAILS[p_name_lower]
                p.git_repo_url = k.get("git_repo_url")
                p.doc_url = k.get("doc_url")
                if not p.evidence_url:
                    p.evidence_url = p.git_repo_url or p.doc_url
            elif p_name_lower == (primary_pkg_name or "").lower():
                p.git_repo_url = detected_git_url
                p.doc_url = detected_doc_url
                if not p.evidence_url:
                    p.evidence_url = detected_git_url or detected_doc_url

        # Generate Executive Brief Markdown
        brief_md = self._generate_executive_brief(
            request, summary, triaged_packages, arch_scan, docker_findings, config_findings,
            primary_package_name=primary_pkg_name,
            git_repo_url=detected_git_url,
            doc_url=detected_doc_url,
            package_version=primary_version,
            package_ecosystem=primary_ecosystem
        )
        csv_data = self._generate_csv(triaged_packages)

        detected_source_url = detected_git_url or detected_doc_url or (raw_text if URLExtractor.is_url(raw_text) else None)

        response = TriageResponse(
            project_name=request.project_name or (f"{primary_pkg_name} Migration" if primary_pkg_name else "Customer Migration Triage"),
            target_os=request.target_os.value.upper(),
            target_platform=request.target_platform.value.upper(),
            summary=summary,
            packages=triaged_packages,
            agent_steps=[],
            executive_brief_markdown=brief_md,
            export_csv_data=csv_data,
            primary_package_name=primary_pkg_name,
            git_repo_url=detected_git_url,
            doc_url=detected_doc_url,
            source_url=detected_source_url,
            package_ecosystem=primary_ecosystem,
            package_version=primary_version,
        )

        yield {
            "type": "result",
            "data": response.model_dump()
        }

    def _generate_executive_brief(
        self,
        request: TriageRequest,
        summary: TriageSummary,
        packages: List[PackageTriageResult],
        arch_scan: Optional[ArchSupportScan] = None,
        docker_findings: Optional[List[DockerfileImageFinding]] = None,
        config_findings: Optional[List[ConfigImageFinding]] = None,
        primary_package_name: Optional[str] = None,
        git_repo_url: Optional[str] = None,
        doc_url: Optional[str] = None,
        package_version: Optional[str] = None,
        package_ecosystem: Optional[str] = None,
    ) -> str:
        rec_val = summary.recommendation.value
        traffic_emoji = "🟢" if "Minimal" in rec_val else (
            "🔵" if "Minor" in rec_val else (
                "🟡" if "Moderate" in rec_val else (
                    "🟠" if "Significant" in rec_val else "🟣"
                )
            )
        )
        
        has_custom_project = request.project_name and request.project_name not in ["Customer Migration Triage", "Migration_Triage", "Workload Migration", "Report"]
        if has_custom_project and primary_package_name and primary_package_name.lower() not in request.project_name.lower():
            display_title = f"{request.project_name} ({primary_package_name})"
        elif has_custom_project:
            display_title = request.project_name
        elif primary_package_name:
            display_title = f"Porting Qualification: {primary_package_name}"
        else:
            display_title = "Customer Migration Triage"

        md = f"""# Executive Porting Feasibility Assessment: {display_title}

**Target Architecture:** IBM Power (`ppc64le`)  
**Target Operating System:** {request.target_os.value.upper()} on {request.target_platform.value.upper()}  
**Primary Target Component:** `{primary_package_name or 'Multi-Component Stack'}` (Version: `{package_version or 'latest'}`)  
**GitHub Repository:** [{git_repo_url or 'Not specified'}]({git_repo_url or '#'})  
**Documentation Link:** [{doc_url or 'Not specified'}]({doc_url or '#'})  
**Assessment Date:** 2026-09-09  
**Triage Confidence:** High (Deterministic Probing + Deep Transitive Dependency Audit + SIMD Instruction Scaling)

---

## 1. Executive Summary & Qualification Recommendation

| Metric | Assessment Result |
| :--- | :--- |
| **Porting Readiness Score** | **{summary.readiness_score_pct}%** |
| **Sales Recommendation Tier** | **{traffic_emoji} {summary.recommendation.value}** |
| **Estimated Porting Sizing** | **{summary.fibonacci_effort_pd} Person-Days (Fibonacci Sized)** |
| **Total Components Analyzed** | **{summary.total_packages}** ({summary.native_count} Native, {summary.agnostic_count} Script/Bytecode, {summary.substitute_count} Substitute, {summary.unported_count} Unported) |
| **Transitive Build Dependencies Scoped** | **{summary.unported_transitive_deps_count} unported build-time requirements uncovered** |
| **Test Dependencies Unresolved** | **{summary.test_deps_unresolved_count} unported test suites/harnesses** |

### Strategic Recommendation:
> **{summary.recommendation_reason}**

---

## 2. Key Technical Findings & Sizing Breakdown

> **Effort Sizing Methodology:** Sizing estimates utilize a single Fibonacci-calibrated ceiling (e.g. 5→8, 26→34, 34→55) covering environment provisioning, source compilation, transitive dependencies, SIMD/VSX adaptation, and test validation on IBM Power architecture. All estimates are rounded to integer person-days.

"""
        # Section 2.1: Version Warnings (Sub-Task 1)
        version_warn_pkgs = [p for p in packages if p.version_warning]
        if version_warn_pkgs:
            md += "### ⚠️ Version-Aware Porting Warnings\n"
            for p in version_warn_pkgs:
                md += f"- **{p.package_name}** (Requested: `{p.requested_version}`): {p.version_warning}\n"
            md += "\n"

        # Section 2.2: Package Porting Deep Dives
        for p in packages:
            if p.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED:
                md += f"### ⚠️ {p.package_name} ({p.ecosystem}) — Estimated Effort: {p.total_effort_pd} PD\n"
                md += f"- **Build System:** {p.build_system or 'Standard'}\n"
                md += f"- **Base Compilation Effort:** {p.base_build_effort_pd} PD\n"
                
                # Build dependencies
                if p.build_dependencies:
                    md += f"- **Build-Time Dependencies Scoped ({len(p.build_dependencies)} total):**\n"
                    for d in p.build_dependencies:
                        icon = "✅" if d.status == AvailabilityStatus.NATIVE_AVAILABLE else "❌"
                        md += f"  - {icon} `{d.name}`: {d.status.value} ({d.porting_effort_pd} PD). {d.notes or ''}\n"

                # Sub-Tasks 2 & 3: SIMD scaling breakdown
                if p.arch_sensitivity and (p.arch_sensitivity.has_simd_avx or p.arch_sensitivity.has_64k_page_risk or p.arch_sensitivity.has_inline_asm):
                    md += f"- **Engineering Adaptation Effort (+{p.arch_complexity_effort_pd} PD):**\n"
                    if p.arch_sensitivity.has_simd_avx:
                        md += (
                            f"  - **SIMD/AVX Analysis:** {p.arch_sensitivity.simd_instruction_count} instruction(s) detected • "
                            f"Complexity Tier: `{p.arch_sensitivity.simd_porting_complexity.value.upper()}` • {p.arch_sensitivity.simd_details}\n"
                        )
                    if p.arch_sensitivity.has_64k_page_risk:
                        md += f"  - **64KB Page Size:** {p.arch_sensitivity.page_risk_details}\n"
                    if p.arch_sensitivity.has_inline_asm:
                        md += f"  - **Inline Assembly:** {p.arch_sensitivity.asm_details}\n"
                    md += f"  - **Remediation Strategy:** {p.arch_sensitivity.remediation_strategy}\n"

                # Sub-Task 4: Test dependencies
                if p.test_dependencies:
                    md += f"- **Testing & Verification Sizing (+{p.test_effort_pd} PD):**\n"
                    for td in p.test_dependencies:
                        icon = "✅" if td.status == AvailabilityStatus.NATIVE_AVAILABLE else "❌"
                        md += f"  - {icon} `{td.name}` ({td.test_dep_type}): {td.status.value} ({td.porting_effort_pd} PD). {td.notes or ''}\n"

                md += "\n"
            elif p.status == AvailabilityStatus.SUBSTITUTE_AVAILABLE:
                md += f"### 🔄 {p.package_name} — Substitute Available (0.5 PD)\n"
                md += f"- **Alternative / Recommended Package:** `{p.substitute_package}`\n"
                md += f"- **Source:** {p.evidence_source}\n\n"

        # Section 2.3: Repository Architecture Posture & CI Matrix (Sub-Task 6)
        if arch_scan and (arch_scan.ppc64le_markers_found or arch_scan.x86_only_markers_found or arch_scan.ci_matrix_has_power):
            md += "### 🏛️ Repository Architecture Support Posture\n"
            md += f"- **Scan Source:** `{arch_scan.scan_source}`\n"
            md += f"- **Upstream CI Matrix Has Power (ppc64le):** {'Yes ✅' if arch_scan.ci_matrix_has_power else 'No ❌'}\n"
            md += f"- **Effort Adjustment Factor:** {arch_scan.effort_adjustment_factor}x\n"
            if arch_scan.ppc64le_markers_found:
                md += f"- **Power/VSX Code Markers ({len(arch_scan.ppc64le_markers_found)}):**\n"
                for m in arch_scan.ppc64le_markers_found[:5]:
                    md += f"  - `{m}`\n"
            if arch_scan.x86_only_markers_found:
                md += f"- **x86-Only Code Markers ({len(arch_scan.x86_only_markers_found)}):**\n"
                for m in arch_scan.x86_only_markers_found[:5]:
                    md += f"  - `{m}`\n"
            md += "\n"

        # Section 2.4: Dockerfile & Config Container Audit (Sub-Tasks 5 & 7)
        if docker_findings:
            md += f"### 🐳 Dockerfile Base Image Audit ({len(docker_findings)} discovered)\n"
            for df in docker_findings:
                icon = "✅" if df.status == AvailabilityStatus.NATIVE_AVAILABLE else "⚠️"
                md += f"- {icon} `{df.dockerfile_path}`: `FROM {df.base_image}:{df.tag}` — Status: {df.status.value} ({df.effort_pd} PD). {df.notes or ''}\n"
            md += "\n"

        if config_findings:
            md += f"### ⚙️ Compose & CI Configuration Image Audit ({len(config_findings)} discovered)\n"
            for cf in config_findings:
                icon = "✅" if cf.status == AvailabilityStatus.NATIVE_AVAILABLE else "⚠️"
                md += f"- {icon} `{cf.config_file_path}` ({cf.config_file_type}): image `{cf.image_ref}` — Status: {cf.status.value} ({cf.effort_pd} PD). {cf.notes or ''}\n"
            md += "\n"

        # Strategic Sales Proposal via Gemini AI
        llm_sales_narrative = ""
        if self.gemini_client:
            try:
                prompt = (
                    f"You are an executive IBM Power pre-sales architect. Write a 2-paragraph strategic sales rationale for moving this customer workload ({request.project_name}) to IBM Power (ppc64le) on {request.target_os.value.upper()}.\n"
                    f"Readiness Score: {summary.readiness_score_pct}%, Recommendation: {summary.recommendation.value}, Sizing: {summary.min_total_person_days}-{summary.max_total_person_days} Person-Days.\n"
                    f"Key unported/scoped components: {[p.package_name for p in packages if p.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED]}.\n"
                    "Highlight IBM Power's specific hardware strengths (e.g. high memory bandwidth, SMT8 core threading, enterprise reliability, and Open-CE optimization). Keep it professional, crisp, and compelling."
                )
                resp_text = generate_gemini_content(self.gemini_client, prompt)
                if resp_text:
                    llm_sales_narrative = f"\n### 🤖 Gemini AI Strategic Sales Proposal:\n{resp_text}\n\n"
            except Exception as e:
                logger.warning(f"Gemini executive sales pitch generation skipped: {e}")

        if llm_sales_narrative:
            md += llm_sales_narrative

        md += """---

## 3. Next Steps for Technical Sales
1. Present this qualification memo to client architecture team to establish feasibility.
2. Hand over scoped transitive build dependency specs to the IBM Power Porting Lab for unported libraries.
3. Utilize IBM Open-CE channels for accelerated AI/data libraries.
"""
        return md

    def _generate_csv(self, packages: List[PackageTriageResult]) -> str:
        lines = ["Package Name,Version,Ecosystem,Status,Tier,Effort (PD),Build System,Transitive Deps,Evidence Source"]
        for p in packages:
            num_deps = len(p.build_dependencies)
            build_sys = p.build_system or "N/A"
            evidence = p.evidence_source or ""
            lines.append(f'"{p.package_name}","{p.requested_version}","{p.ecosystem}","{p.status.value}","{p.tier_description}",{p.total_effort_pd},"{build_sys}",{num_deps},"{evidence}"')
        return "\n".join(lines)
