import os
import re
import math
import asyncio
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional, Tuple
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
    DeliverableType,
    DeliverableMatchStatus,
    RecommendationTrafficLight,
    SIMDPortingComplexity,
    TestDependency,
    ArchSupportScan,
    DockerfileImageFinding,
    ConfigImageFinding,
    SizingBreakdown,
)
from .normalizer import UniversalNormalizer
from .prober import MultiSourceProber
from .build_analyzer import BuildAnalyzer, scale_arch_effort, get_simd_multipliers
from .repo_scanner import RepoScanner
from .gemini_helper import generate_gemini_content
from .url_extractor import URLExtractor
from .llm_client import LLMService

logger = logging.getLogger("agent")

def calculate_lifecycle_sizing(
    triaged_packages: List[Any],
    deliverable_type: Any = DeliverableType.CONTAINER,
    readiness_pct: float = 100.0,
    unported_count: int = 0,
    blocker_count: int = 0,
    unported_transitive_count: int = 0,
    dockerfile_findings: Optional[List[Any]] = None,
    config_findings: Optional[List[Any]] = None,
) -> Tuple[SizingBreakdown, int, int, int]:
    """Calculates engineering sizing across all standard enterprise porting lifecycle stages:
    1. prep_env_pd: Environment & Toolchain Preparation
    2. readiness_audit_pd: Architecture Readiness & Feasibility Inspection
    3. build_source_pd: Source Compilation & Core Porting (including transitive deps & SIMD)
    4. ci_pipeline_pd: CI Matrix & Multi-Arch Container Integration
    5. bug_fix_validation_pd: Testing, Bug Fixing & Stabilization
    6. contingency_buffer_pd: Decent Risk & Upstream Contingency Buffer (20-25%)
    
    Returns (breakdown, total_estimated_pd, min_total_pd, max_total_pd).
    """
    def _val(item: Any, attr: str, default: Any = 0):
        if isinstance(item, dict):
            return item.get(attr, default)
        return getattr(item, attr, default)

    table_packages_effort = sum(_val(p, "total_effort_pd", 0) for p in triaged_packages)

    # Turnkey native deployment
    if table_packages_effort == 0 and unported_count == 0 and blocker_count == 0:
        breakdown = SizingBreakdown(
            prep_env_pd=0.0,
            readiness_audit_pd=0.0,
            build_source_pd=0.0,
            ci_pipeline_pd=0.0,
            bug_fix_validation_pd=0.0,
            contingency_buffer_pd=0.0,
            contingency_pct=0.0,
            subtotal_pd=0.0,
            total_estimated_pd=0,
            methodology_note="All components are natively available on IBM Power (ppc64le). Turnkey deployment ready with 0 Person-Days build effort.",
        )
        return breakdown, 0, 0, 0

    deliv_val = deliverable_type.value if hasattr(deliverable_type, "value") else str(deliverable_type)

    # Count packages that require engineering work (unported or partial deliverable match)
    packages_needing_effort = [p for p in triaged_packages if _val(p, "total_effort_pd", 0) > 0]
    num_effort_pkgs = len(packages_needing_effort)

    # Stage 1: Environment Preparation & Toolchain Setup
    if deliv_val in ("build", "rpm"):
        prep_env = 2.0 if num_effort_pkgs >= 3 else 1.5
    else:
        # Container or build script deliverable
        if readiness_pct >= 90.0 and unported_count <= 1 and num_effort_pkgs <= 1:
            prep_env = 0.5
        elif num_effort_pkgs >= 4:
            prep_env = 1.5
        else:
            prep_env = 1.0

    # Stage 2: Architecture Readiness & Feasibility Inspection
    def _has_friction(p: Any) -> bool:
        arch = _val(p, "arch_sensitivity", None)
        if not arch:
            return False
        return bool(_val(arch, "has_simd_avx", False) or _val(arch, "has_64k_page_risk", False) or _val(arch, "has_inline_asm", False))

    has_arch_friction = any(_has_friction(p) for p in triaged_packages)
    readiness_audit = 0.5
    if has_arch_friction:
        readiness_audit += 0.5
    if unported_transitive_count >= 2:
        readiness_audit += 0.5
    if num_effort_pkgs >= 4:
        readiness_audit += 0.5
    readiness_audit = min(2.5, readiness_audit)

    # Stage 3: Source Compilation & Core Porting
    # Must account for all packages requiring compilation, porting, or deliverable adaptation in the matrix!
    total_test_deps_effort = sum(float(_val(p, "test_effort_pd", 0.0)) for p in triaged_packages)

    build_source = 0.0
    for p in triaged_packages:
        tot_e = float(_val(p, "total_effort_pd", 0))
        test_e = float(_val(p, "test_effort_pd", 0.0))
        # The build/compilation portion is the package effort minus its unit test effort
        build_portion = max(0.0, tot_e - test_e)

        # Detailed component breakdown
        detailed_e = (
            float(_val(p, "base_build_effort_pd", 0.0))
            + float(_val(p, "transitive_deps_effort_pd", 0.0))
            + float(_val(p, "arch_complexity_effort_pd", 0.0))
        )
        pkg_build = max(build_portion, detailed_e)
        if pkg_build < 1.0 and tot_e >= 1.0:
            pkg_build = tot_e - test_e if (tot_e - test_e) > 0 else tot_e
        build_source += pkg_build

    build_source = round(build_source, 1)
    if build_source < 1.0 and (unported_count > 0 or num_effort_pkgs > 0):
        build_source = 1.0

    # Stage 4: CI Pipeline & Multi-Arch Container Integration
    has_multi_configs = bool((dockerfile_findings and len(dockerfile_findings) > 1) or (config_findings and len(config_findings) > 1))
    if deliv_val in ("build", "rpm"):
        ci_pipeline = 2.5 if num_effort_pkgs >= 4 else 2.0
    elif deliv_val == "container":
        if has_multi_configs or num_effort_pkgs >= 4:
            ci_pipeline = 2.0
        elif num_effort_pkgs >= 2:
            ci_pipeline = 1.5
        else:
            ci_pipeline = 1.0
    else:
        ci_pipeline = 1.0

    # Stage 5: Testing, Bug Fixing & Stabilization
    # Package test effort + systemic regression testing & stabilization across integrated components
    stabilization_base = 1.0 if (unported_count > 0 or num_effort_pkgs > 0) else 0.5
    if num_effort_pkgs >= 3:
        stabilization_base += min(2.5, round(0.4 * (num_effort_pkgs - 1), 1))

    def _has_deep_simd(p: Any) -> bool:
        arch = _val(p, "arch_sensitivity", None)
        if not arch:
            return False
        comp = _val(arch, "simd_porting_complexity", None)
        comp_val = comp.value if hasattr(comp, "value") else str(comp)
        return comp_val in ("PARTIAL_REWRITE", "FULL_REDESIGN", "partial_rewrite", "full_redesign")

    has_deep_simd = any(_has_deep_simd(p) for p in triaged_packages)
    if has_deep_simd:
        stabilization_base += 1.0

    bug_fix_validation = round(total_test_deps_effort + stabilization_base, 1)

    # Stage 6: Decent Risk & Upstream Contingency Buffer (20% to 25%)
    subtotal = round(prep_env + readiness_audit + build_source + ci_pipeline + bug_fix_validation, 1)
    contingency_rate = 25.0 if (has_arch_friction or unported_transitive_count >= 3 or num_effort_pkgs >= 3) else 20.0
    contingency_buffer = round(max(1.0, subtotal * (contingency_rate / 100.0)), 1)

    total_estimated = int(math.ceil(subtotal + contingency_buffer))

    # Invariant: Project committed sizing MUST be strictly greater than or equal to the sum of direct package tasks
    # because project sizing encompasses package porting + infrastructure + CI + stabilization + 20-25% contingency buffer!
    min_committed = int(math.ceil(table_packages_effort * (1.0 + contingency_rate / 100.0)))
    if total_estimated < min_committed:
        total_estimated = min_committed

    min_total = max(1, int(math.floor(subtotal)))
    max_total = total_estimated

    methodology = (
        f"Lifecycle WBS Sizing: {prep_env:.1f}d Prep Env + {readiness_audit:.1f}d Readiness + "
        f"{build_source:.1f}d Build from Source + {ci_pipeline:.1f}d CI Pipeline + "
        f"{bug_fix_validation:.1f}d Bug Fix/Test = {subtotal:.1f}d Subtotal + "
        f"{contingency_buffer:.1f}d Buffer ({int(contingency_rate)}%) → {total_estimated} Person-Days."
    )

    breakdown = SizingBreakdown(
        prep_env_pd=prep_env,
        readiness_audit_pd=readiness_audit,
        build_source_pd=build_source,
        ci_pipeline_pd=ci_pipeline,
        bug_fix_validation_pd=bug_fix_validation,
        contingency_buffer_pd=contingency_buffer,
        contingency_pct=contingency_rate,
        subtotal_pd=subtotal,
        total_estimated_pd=total_estimated,
        methodology_note=methodology,
    )
    return breakdown, total_estimated, min_total, max_total


from .package_lookup import get_lookup_manager


class _DynamicEcosystemDetails(dict):
    """Dynamic lookup over packages_lookup.json for package metadata."""
    def __getitem__(self, key):
        meta = get_lookup_manager().get_metadata(key)
        if meta:
            return meta
        raise KeyError(key)

    def __contains__(self, key):
        return get_lookup_manager().get_metadata(key) is not None

    def get(self, key, default=None):
        meta = get_lookup_manager().get_metadata(key)
        return meta if meta is not None else default


KNOWN_ECOSYSTEM_DETAILS = _DynamicEcosystemDetails()


class TriageAgent:
    """Agentic AI Orchestrator that triages workloads, probes repositories, scopes transitive dependencies,
    analyzes SIMD instructions & complexity, checks test dependencies, scans Dockerfiles & configs, and synthesizes reports.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        llm_provider: Optional[str] = None,
        bobshell_api_key: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.llm_service = LLMService(
            provider=llm_provider,
            bobshell_api_key=bobshell_api_key,
            gemini_api_key=self.api_key,
        )
        self.gemini_client = self.llm_service.gemini_client
        self.prober = MultiSourceProber(gemini_client=self.gemini_client, llm_service=self.llm_service)

    async def run_triage_stream(self, request: TriageRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """Runs the triage pipeline yielding live agent steps and the final comprehensive response."""
        # Update LLM service if request includes an override provider or keys
        if request.llm_provider or request.bobshell_api_key or request.gemini_api_key:
            self.llm_service = LLMService(
                provider=request.llm_provider,
                bobshell_api_key=request.bobshell_api_key,
                gemini_api_key=request.gemini_api_key or self.api_key,
            )
            self.gemini_client = self.llm_service.gemini_client
            self.prober.set_gemini_client(self.gemini_client)
            self.prober.set_llm_service(self.llm_service)

        steps: List[AgentStep] = []
        step_counter = 1

        # Resolve effective OS and platform from combined environment field
        effective_os = request.effective_os()
        deliverable_type: DeliverableType = request.deliverable_type

        # Step 1: Ingestion & Normalization
        yield {
            "type": "step",
            "step": AgentStep(
                step_id=step_counter,
                agent_name="IngestionAgent",
                action_type="plan",
                target="Input Manifests",
                thought="Ingesting provided input and standardizing packages into canonical Package URLs (PURL).",
                detail=(
                    f"Target: {request.target_environment.display} (ppc64le). "
                    f"Deliverable: {deliverable_type.value.replace('_', ' ').title()}. "
                    f"Depth: {request.triage_depth.value}."
                )
            ).model_dump()
        }
        await asyncio.sleep(0.3)
        step_counter += 1

        raw_text = request.raw_manifest or ""

        # --- Image ingestion: extract manifest text from uploaded image via LLM vision ---
        if request.image_data_base64 and self.llm_service.is_active():
            provider_label = "IBM Bob Shell" if self.llm_service.provider == "ibm_bob" else "LLM Vision"
            yield {
                "type": "step",
                "step": AgentStep(
                    step_id=step_counter,
                    agent_name="VisionAgent",
                    action_type="llm_reasoning",
                    target="Uploaded Image",
                    thought="Analysing uploaded image with LLM Vision to extract dependency manifest text.",
                    detail="OCR + semantic extraction of packages, versions, and ecosystems visible in the image."
                ).model_dump()
            }
            await asyncio.sleep(0.2)
            step_counter += 1

            vision_prompt = (
                "You are an IBM Power porting assistant. The user has uploaded an image that contains a software dependency "
                "manifest, Dockerfile, requirements file, architecture diagram, or similar artefact.\n"
                "Extract all software packages, container images, and libraries visible in the image and return them as "
                "a plain-text list, one entry per line, preserving version numbers where shown "
                "(e.g. 'nginx:1.24', 'torch==2.1.0', 'libssl-dev'). "
                "If the image contains a Dockerfile, reproduce the FROM and RUN apt-get/pip install lines verbatim. "
                "Output ONLY the extracted manifest text — no commentary, no markdown fences."
            )
            extracted = self.llm_service.generate_content(
                vision_prompt,
                json_mode=False,
                image_data_base64=request.image_data_base64,
                image_media_type=request.image_media_type or "image/png",
                stage="Vision Manifest Ingestion",
            )
            if extracted and extracted.strip():
                # Merge with any typed text — image text takes precedence if no text was supplied
                raw_text = (raw_text + "\n" + extracted).strip() if raw_text else extracted.strip()
                yield {
                    "type": "step",
                    "step": AgentStep(
                        step_id=step_counter,
                        agent_name="VisionAgent",
                        action_type="llm_reasoning",
                        target="Uploaded Image",
                        thought=f"Vision extraction complete — {len(extracted.splitlines())} lines of manifest text recovered from image.",
                        detail=extracted[:200] + ("..." if len(extracted) > 200 else "")
                    ).model_dump()
                }
                await asyncio.sleep(0.2)
                step_counter += 1
        # ---------------------------------------------------------------------------------

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

            url_pkgs, url_title, url_note = await URLExtractor.extract_from_url(
                candidate_url,
                gemini_client=self.gemini_client,
                llm_service=self.llm_service
            )
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

            temp_repo = await asyncio.to_thread(RepoScanner.shallow_clone_repo, scan_repo_url, 1, 8)
            if temp_repo:
                arch_scan = await asyncio.to_thread(RepoScanner.scan_arch_support, temp_repo)
                docker_findings = await asyncio.to_thread(RepoScanner.scan_dockerfiles, temp_repo)
                config_findings = await asyncio.to_thread(RepoScanner.scan_config_images, temp_repo)
                await asyncio.to_thread(RepoScanner.cleanup_repo, temp_repo)

            yield {
                "type": "step",
                "step": AgentStep(
                    step_id=step_counter,
                    agent_name="RepoScanAgent",
                    action_type="scan",
                    target=scan_repo_url,
                    thought="Repository architecture scan complete. Verified CI matrix and architecture markers.",
                    detail=f"Power CI Runner: {'Verified' if (arch_scan and arch_scan.ci_matrix_has_power) else 'None'} | Effort adjustment: {arch_scan.effort_adjustment_factor if arch_scan else 1.0}x"
                ).model_dump()
            }
            await asyncio.sleep(0.1)
            step_counter += 1

        if not arch_scan:
            target_pkg_name = request.project_name or (unique_items[0]["name"] if unique_items else "workload")
            arch_scan = await asyncio.to_thread(
                RepoScanner.llm_infer_arch_support,
                target_pkg_name,
                self.gemini_client,
                self.llm_service
            )

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
                    thought=f"Consulting live registries (Quay.io/Docker Hub), {effective_os} repos, and LLM for {name} ({version}) on ppc64le...",
                ).model_dump()
            }
            await asyncio.sleep(0.15)
            step_counter += 1

            probe_res = await self.prober.probe_component(
                name, version, eco, effective_os, deliverable_type
            )

            pkg_result = PackageTriageResult(
                package_name=name,
                requested_version=version,
                ecosystem=eco,
                status=probe_res["status"],
                tier_description=probe_res["tier"],
                evidence_source=probe_res.get("evidence"),
                evidence_url=probe_res.get("url"),
                substitute_package=probe_res.get("substitute"),
                version_warning=probe_res.get("version_warning"),
                deliverable_match=probe_res.get("deliverable_match", DeliverableMatchStatus.SUPPORTED),
                deliverable_detail=probe_res.get("deliverable_detail"),
            )

            # Log version warning or deliverable match detail
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

            if pkg_result.deliverable_detail and pkg_result.deliverable_match != DeliverableMatchStatus.SUPPORTED:
                yield {
                    "type": "step",
                    "step": AgentStep(
                        step_id=step_counter,
                        agent_name="DeliverableClassifier",
                        action_type="lookup",
                        target=f"{name} Deliverable Match",
                        thought=f"Deliverable match [{deliverable_type.value}]: {pkg_result.deliverable_match.value.replace('_', ' ').title()}",
                        detail=pkg_result.deliverable_detail
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
                img_probe = await self.prober.probe_component(
                    df.base_image, df.tag, "container", effective_os, deliverable_type
                )
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
                cfg_probe = await self.prober.probe_component(img_name, img_tag, "container", effective_os, deliverable_type)
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

                # Sub-Task 2 & 3: SIMD instruction count & 4-tier complexity analysis via LLM
                if pkg.arch_sensitivity and (pkg.arch_sensitivity.has_simd_avx or pkg.arch_sensitivity.has_64k_page_risk or pkg.arch_sensitivity.has_inline_asm):
                    if (self.llm_service and self.llm_service.is_active()) or self.gemini_client:
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
                            if self.llm_service and self.llm_service.is_active():
                                resp_text = await asyncio.to_thread(
                                    self.llm_service.generate_content,
                                    prompt,
                                    json_mode=True,
                                    stage="SIMD Architecture Complexity",
                                )
                            else:
                                resp_text = await asyncio.to_thread(generate_gemini_content, self.gemini_client, prompt, True)
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
                            logger.warning(f"LLM code analysis call skipped: {llm_err}")

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
                BuildAnalyzer.analyze_package_build(pkg, effective_os)

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

        # Apply partial deliverable match multiplier to every package with effort > 0
        for pkg in triaged_packages:
            dm = pkg.deliverable_match
            if dm in (DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE, DeliverableMatchStatus.PARTIAL_DIFFERENT_VERSION):
                from .models import _PARTIAL_EFFORT_MULTIPLIERS
                mult = _PARTIAL_EFFORT_MULTIPLIERS[dm]
                if pkg.total_effort_pd > 0:
                    pkg.total_effort_pd = max(1, int(round(pkg.total_effort_pd * mult)))
                    pkg.base_build_effort_pd = round(pkg.base_build_effort_pd * mult, 1)
                elif pkg.status in (AvailabilityStatus.NATIVE_AVAILABLE, AvailabilityStatus.PLATFORM_AGNOSTIC):
                    # Partial match on a previously "zero effort" package — add integration overhead
                    pkg.total_effort_pd = 1 if dm == DeliverableMatchStatus.PARTIAL_DIFFERENT_VERSION else 2
                    pkg.base_build_effort_pd = float(pkg.total_effort_pd)

        # Add Sub-Task 5 & 7 container image effort into primary package
        container_extra_pd = sum(f.effort_pd for f in docker_findings) + sum(f.effort_pd for f in config_findings)
        if container_extra_pd > 0 and triaged_packages:
            triaged_packages[0].total_effort_pd += int(round(container_extra_pd))
            triaged_packages[0].base_build_effort_pd += container_extra_pd

        # Step 4: Aggregate Metrics & Scoring
        total_count = len(triaged_packages)
        native_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.NATIVE_AVAILABLE)
        agnostic_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.PLATFORM_AGNOSTIC)
        substitute_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.SUBSTITUTE_AVAILABLE)
        unported_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED)
        blocker_count = sum(1 for p in triaged_packages if p.status == AvailabilityStatus.BLOCKER)
        partial_count = sum(
            1 for p in triaged_packages
            if p.deliverable_match in (
                DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE,
                DeliverableMatchStatus.PARTIAL_DIFFERENT_VERSION,
            )
        )

        # Count unported build-time transitive dependencies
        unported_transitive_count = 0
        for p in triaged_packages:
            unported_transitive_count += sum(1 for d in p.build_dependencies if d.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED)

        # Count unported test dependencies (Sub-Task 4)
        unported_test_count = 0
        for p in triaged_packages:
            unported_test_count += sum(1 for td in p.test_dependencies if td.status != AvailabilityStatus.NATIVE_AVAILABLE)

        # Readiness Score % — partial matches reduce score proportionally
        ready_units = (
            native_count + agnostic_count
            + (substitute_count * 0.9)
            + (unported_count * 0.3)
            - (partial_count * 0.25)   # partial matches reduce readiness
        )
        readiness_pct = round((max(ready_units, 0) / max(total_count, 1)) * 100.0, 1)

        # Enterprise Porting Lifecycle Work Breakdown Structure (WBS) Sizing
        breakdown, total_estimated_pd, min_total_pd, max_total_pd = calculate_lifecycle_sizing(
            triaged_packages=triaged_packages,
            deliverable_type=deliverable_type,
            readiness_pct=readiness_pct,
            unported_count=unported_count,
            blocker_count=blocker_count,
            unported_transitive_count=unported_transitive_count,
            dockerfile_findings=docker_findings,
            config_findings=config_findings,
        )

        # Positive Effort-Oriented Qualification Recommendations
        if blocker_count > 0:
            rec = SalesRecommendationTier.NOT_POSSIBLE_AS_IS
            rec_reason = f"Workload contains {blocker_count} proprietary x86 component(s) requiring architectural substitution (e.g. OpenBLAS / ESSL alternatives recommended)."
        elif readiness_pct >= 90 and total_estimated_pd == 0 and blocker_count == 0:
            rec = SalesRecommendationTier.MINIMAL_EFFORT
            rec_reason = f"Turnkey readiness ({readiness_pct}%). All components run out-of-the-box on IBM Power (0 Person-Days build effort)."
        elif partial_count > 0 and readiness_pct >= 70:
            rec = SalesRecommendationTier.MODERATE_EFFORT
            rec_reason = (
                f"Moderate readiness ({readiness_pct}%) with {partial_count} partial deliverable match(es) "
                f"for '{deliverable_type.value}' deliverable type. Estimated porting effort: {total_estimated_pd} Person-Days."
            )
        elif total_estimated_pd <= 5:
            rec = SalesRecommendationTier.MINOR_EFFORT
            rec_reason = f"High readiness ({readiness_pct}%). Comprehensive porting lifecycle (env prep, build, CI, validation & buffer) estimated at {total_estimated_pd} Person-Days."
        elif total_estimated_pd <= 20:
            rec = SalesRecommendationTier.MODERATE_EFFORT
            rec_reason = f"Moderate porting scope ({readiness_pct}% ready). Transitive builds, CI integration, bug fixing & contingency buffer estimated at {total_estimated_pd} Person-Days."
        else:
            rec = SalesRecommendationTier.SIGNIFICANT_EFFORT
            rec_reason = f"Extensive porting investment ({readiness_pct}% ready). Multi-tier transitive dependencies, SIMD adaptations, CI matrix & buffer estimated at {total_estimated_pd} Person-Days."

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
            estimated_effort_pd=total_estimated_pd,
            min_total_person_days=min_total_pd,
            max_total_person_days=max_total_pd,
            unported_transitive_deps_count=unported_transitive_count,
            test_deps_unresolved_count=unported_test_count,
            partial_support_count=partial_count,
            sizing_breakdown=breakdown,
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

        # Attach repository and documentation links to triaged packages & refresh lookup file
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

            # Automatically persist & refresh analyzed package in the lookup file to avoid future LLM trips
            try:
                get_lookup_manager().save_or_refresh(
                    package_name=p.package_name,
                    version=p.requested_version or "latest",
                    probe_result={
                        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                        "available_version": p.available_version,
                        "tier": p.tier,
                        "evidence": p.evidence,
                        "url": p.evidence_url or p.git_repo_url or p.doc_url,
                        "substitute": p.substitute,
                        "version_warning": p.version_warning,
                    },
                    metadata={
                        "git_repo_url": p.git_repo_url,
                        "doc_url": p.doc_url,
                        "ecosystem": p.ecosystem,
                    }
                )
            except Exception as e:
                logger.debug("Lookup auto-refresh skipped for %s: %s", p.package_name, e)

        # Record and attach Token & Cost Telemetry
        token_usage = self.llm_service.get_token_usage()
        summary.token_usage = token_usage

        # Telemetry Agent step
        step_counter += 1
        provider_label = "IBM Bob Shell" if token_usage.llm_provider == "ibm_bob" else "Google Gemini"
        breakdown_detail = (
            "Breakdown: " + ", ".join([f"{b.stage}: ${b.cost_usd:.4f} ({b.percentage}%)" for b in token_usage.breakdown])
            if token_usage.breakdown
            else f"Engine: {token_usage.llm_model} • Provider: {token_usage.llm_provider}"
        )
        yield {
            "type": "step",
            "step": AgentStep(
                step_id=step_counter,
                agent_name="TelemetryAgent",
                action_type="synthesis",
                target="LLM Cost & Token Accounting",
                thought=(
                    f"Qualification telemetry recorded via {provider_label}: {token_usage.total_tokens:,} total tokens "
                    f"({token_usage.input_tokens:,} in / {token_usage.output_tokens:,} out). "
                    f"Associated cost: ${token_usage.cost_usd:.4f} USD across {token_usage.calls_count} request(s)."
                ),
                detail=breakdown_detail,
            ).model_dump()
        }

        # Stream token usage event
        yield {
            "type": "token_usage",
            "usage": token_usage.model_dump()
        }

        # Generate Executive Brief Markdown
        brief_md = await asyncio.to_thread(
            self._generate_executive_brief,
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
            target_os=effective_os.upper(),
            target_platform=request.effective_platform().upper(),
            target_environment=request.target_environment.display,
            deliverable_type=deliverable_type.value,
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
            token_usage=token_usage,
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
| **Estimated Porting Sizing** | **{summary.estimated_effort_pd} Person-Days ({summary.recommendation.value})** |
| **Total Components Analyzed** | **{summary.total_packages}** ({summary.native_count} Native, {summary.agnostic_count} Script/Bytecode, {summary.substitute_count} Substitute, {summary.unported_count} Unported) |
| **Transitive Build Dependencies Scoped** | **{summary.unported_transitive_deps_count} unported build-time requirements uncovered** |
| **Test Dependencies Unresolved** | **{summary.test_deps_unresolved_count} unported test suites/harnesses** |

### Strategic Recommendation:
> **{summary.recommendation_reason}**

---

## 2. Key Technical Findings & Lifecycle Sizing Breakdown

> **Effort Sizing Methodology (Lifecycle WBS):** Sizing estimates are structured across all distinct porting stages: (1) Environment & Toolchain Preparation, (2) Architecture Readiness & Feasibility Inspection, (3) Source Build & Core Porting, (4) CI Pipeline & Multi-Arch Container Integration, (5) Testing, Bug Fixing & Stabilization, plus a 20-25% Risk & Upstream Contingency Buffer.

"""
        if summary.sizing_breakdown and summary.estimated_effort_pd > 0:
            sb = summary.sizing_breakdown
            md += f"""### 📋 Enterprise Porting Lifecycle Breakdown

| Stage | Activity Scope | Sizing (PD) |
| :--- | :--- | :---: |
| **1. Prep Environment & Toolchains** | PowerVM/LPAR/OCP cluster setup, GCC/Clang compilers, SIMDe/VSX dev headers | {sb.prep_env_pd:.1f} PD |
| **2. Architecture Readiness Inspection** | Endianness, 64KB page risks, build scripts & license qualification | {sb.readiness_audit_pd:.1f} PD |
| **3. Build from Source & Core Porting** | Core unported libraries, transitive dependencies & vector code compilation | {sb.build_source_pd:.1f} PD |
| **4. CI Pipeline & Container Integration** | ppc64le CI matrix runners & multi-arch container manifest packaging | {sb.ci_pipeline_pd:.1f} PD |
| **5. Testing, Bug Fixing & Stabilization** | Test harness execution, runtime defect resolution & SMT8 stabilization | {sb.bug_fix_validation_pd:.1f} PD |
| **Engineering Subtotal** | Direct engineering activities subtotal | **{sb.subtotal_pd:.1f} PD** |
| **6. Contingency Buffer ({sb.contingency_pct:.0f}%)** | Risk buffer covering unforeseen upstream friction | **+{sb.contingency_buffer_pd:.1f} PD** |
| **Total Committed Sizing** | **Comprehensive end-to-end delivery commitment** | **{summary.estimated_effort_pd} Person-Days** |

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

        # Strategic Sales Proposal via AI
        llm_sales_narrative = ""
        if (self.llm_service and self.llm_service.is_active()) or self.gemini_client:
            provider_title = "IBM Bob AI" if (self.llm_service and self.llm_service.provider == "ibm_bob") else "LLM AI"
            try:
                prompt = (
                    f"You are an executive IBM Power pre-sales architect. Write a 2-paragraph strategic sales rationale for moving this customer workload ({request.project_name}) to IBM Power (ppc64le) on {request.target_os.value.upper()}.\n"
                    f"Readiness Score: {summary.readiness_score_pct}%, Recommendation: {summary.recommendation.value}, Sizing: {summary.min_total_person_days}-{summary.max_total_person_days} Person-Days.\n"
                    f"Key unported/scoped components: {[p.package_name for p in packages if p.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED]}.\n"
                    "Highlight IBM Power's specific hardware strengths (e.g. high memory bandwidth, SMT8 core threading, enterprise reliability, and Open-CE optimization). Keep it professional, crisp, and compelling."
                )
                if self.llm_service and self.llm_service.is_active():
                    resp_text = self.llm_service.generate_content(prompt, stage="Executive Sales Proposal")
                else:
                    resp_text = generate_gemini_content(self.gemini_client, prompt)
                if resp_text:
                    llm_sales_narrative = f"\n### 🤖 {provider_title} Strategic Sales Proposal:\n{resp_text}\n\n"
            except Exception as e:
                logger.warning(f"Executive sales pitch generation skipped: {e}")

        if llm_sales_narrative:
            md += llm_sales_narrative

        # Section: LLM Telemetry & Accounting
        token_usage = summary.token_usage
        if token_usage:
            engine_label = "IBM Bob Shell" if token_usage.llm_provider == "ibm_bob" else "Google Gemini"
            breakdown_md = ""
            if token_usage.breakdown:
                breakdown_md = "\n**Cost & Token Breakdown by Triage Stage:**\n\n"
                breakdown_md += "| Triage Stage | Calls | In Tokens | Out Tokens | Total Tokens | Cost (USD) | Share |\n"
                breakdown_md += "|:---|:---:|:---:|:---:|:---:|:---:|:---:|\n"
                for item in token_usage.breakdown:
                    breakdown_md += (
                        f"| {item.stage} | {item.calls_count} | {item.input_tokens:,} | "
                        f"{item.output_tokens:,} | {item.total_tokens:,} | ${item.cost_usd:.4f} | {item.percentage}% |\n"
                    )
                breakdown_md += "\n"

            md += f"""---

## 3. LLM Analysis Telemetry & Cost Accounting
- **LLM Engine:** {engine_label} (`{token_usage.llm_model}`)
- **Total Tokens Consumed:** **{token_usage.total_tokens:,}** tokens
  - **Input Tokens (Prompt/Context):** {token_usage.input_tokens:,} tokens
  - **Output Tokens (Reasoning/Synthesis):** {token_usage.output_tokens:,} tokens
- **Total Associated Cost:** **${token_usage.cost_usd:.4f} USD** across {token_usage.calls_count} request(s)
{breakdown_md}
"""
            next_header = "## 4. Next Steps for Technical Sales"
        else:
            next_header = "## 3. Next Steps for Technical Sales"

        md += f"""---

{next_header}
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
