from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TargetEnvironment(str, Enum):
    """Combined OS + platform for Power deployments (ppc64le)."""
    RHEL9_OCP   = "rhel9_ocp"
    RHEL10_OCP  = "rhel10_ocp"
    RHEL9_BARE  = "rhel9_baremetal"
    RHEL10_BARE = "rhel10_baremetal"

    @property
    def os(self) -> str:
        return "rhel9" if self.value.startswith("rhel9") else "rhel10"

    @property
    def platform(self) -> str:
        return "ocp" if self.value.endswith("ocp") else "baremetal"

    @property
    def display(self) -> str:
        names = {
            "rhel9_ocp":       "OpenShift Platform (ppc64le)",
            "rhel10_ocp":      "OpenShift Platform — RHEL 10 (ppc64le)",
            "rhel9_baremetal": "Bare Metal / PowerVM — RHEL 9 (ppc64le)",
            "rhel10_baremetal":"Bare Metal / PowerVM — RHEL 10 (ppc64le)",
        }
        return names.get(self.value, self.value)


# Keep old enums as aliases so existing serialised responses are not broken.
class TargetOS(str, Enum):
    RHEL8    = "rhel8"
    RHEL9    = "rhel9"
    RHEL10   = "rhel10"
    UBUNTU22 = "ubuntu22"
    UBUNTU24 = "ubuntu24"
    SLES15   = "sles15"


class TargetPlatform(str, Enum):
    BARE_METAL = "baremetal"
    POWER_VM   = "powervm"
    OPENSHIFT  = "ocp"


class DeliverableType(str, Enum):
    """The type of artefact the customer intends to deploy on Power."""
    CONTAINER    = "container"    # OCI container image
    BUILD        = "build"        # compiled binary / wheel / RPM built from source
    BUILD_SCRIPT = "build_script" # existing build script / recipe available


class DeliverableMatchStatus(str, Enum):
    """
    How well the available artefact on ppc64le matches the requested deliverable type.
    Used in place of—or alongside—AvailabilityStatus for human-readable output.
    """
    SUPPORTED                   = "supported"
    PARTIAL_DIFFERENT_TYPE      = "partial_different_type"
    PARTIAL_DIFFERENT_VERSION   = "partial_different_version"
    NOT_SUPPORTED               = "not_supported"


# Effort multipliers applied when match is only partial
_PARTIAL_EFFORT_MULTIPLIERS: Dict[DeliverableMatchStatus, float] = {
    DeliverableMatchStatus.SUPPORTED:                 1.0,
    DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE:    1.5,   # extra integration / adaptation work
    DeliverableMatchStatus.PARTIAL_DIFFERENT_VERSION: 1.25,  # backport / upgrade effort
    DeliverableMatchStatus.NOT_SUPPORTED:             1.0,   # already blocker/unported — no extra multiplier
}


class TriageDepth(str, Enum):
    EXPRESS = "express"
    DEEP    = "deep"


class AvailabilityStatus(str, Enum):
    NATIVE_AVAILABLE         = "native_available"
    PLATFORM_AGNOSTIC        = "platform_agnostic"
    SUBSTITUTE_AVAILABLE     = "substitute_available"
    UNPORTED_BUILD_REQUIRED  = "unported_build_required"
    BLOCKER                  = "blocker"


# v4: positive effort-oriented tiers (Fibonacci sizing)
class SalesRecommendationTier(str, Enum):
    MINIMAL_EFFORT      = "Minimal Effort"
    MINOR_EFFORT        = "Minor Effort"
    MODERATE_EFFORT     = "Moderate Effort"
    SIGNIFICANT_EFFORT  = "Significant Effort"
    NOT_POSSIBLE_AS_IS  = "Not Possible As-Is (Alternative Required)"


# Backward compatibility alias kept so existing callers still work
RecommendationTrafficLight = SalesRecommendationTier


class SIMDPortingComplexity(str, Enum):
    DIRECT         = "DIRECT"
    SIMDE_COMPATIBLE = "SIMDE_COMPATIBLE"
    PARTIAL_REWRITE  = "PARTIAL_REWRITE"
    FULL_REDESIGN    = "FULL_REDESIGN"


class ArchSensitivity(BaseModel):
    has_simd_avx: bool = False
    simd_details: Optional[str] = None
    simd_instruction_count: int = 0
    simd_porting_complexity: SIMDPortingComplexity = SIMDPortingComplexity.DIRECT
    base_engineering_effort_pd: float = 0.0
    simd_instruction_multiplier: float = 1.0
    simd_complexity_multiplier: float = 1.0
    has_inline_asm: bool = False
    asm_details: Optional[str] = None
    has_64k_page_risk: bool = False
    page_risk_details: Optional[str] = None
    has_endianness_risk: bool = False
    has_custom_jit: bool = False
    remediation_strategy: Optional[str] = None
    code_snippet: Optional[str] = None


class ToolchainRequirement(BaseModel):
    tool: str
    required_version: str
    ppc64le_supported: bool = True
    notes: Optional[str] = None


class BuildDependency(BaseModel):
    name: str
    version: Optional[str] = None
    purpose: str = "BuildRequires"
    status: AvailabilityStatus = AvailabilityStatus.NATIVE_AVAILABLE
    evidence_source: Optional[str] = None
    porting_effort_pd: float = 0.0
    notes: Optional[str] = None
    transitive_children: List["BuildDependency"] = Field(default_factory=list)


class TestDependency(BaseModel):
    __test__ = False
    name: str
    version: Optional[str] = None
    test_dep_type: str = "framework"
    status: AvailabilityStatus = AvailabilityStatus.NATIVE_AVAILABLE
    evidence_source: Optional[str] = None
    porting_effort_pd: float = 0.0
    notes: Optional[str] = None


class ArchSupportScan(BaseModel):
    ppc64le_markers_found: List[str] = Field(default_factory=list)
    x86_only_markers_found: List[str] = Field(default_factory=list)
    ci_matrix_has_power: bool = False
    scan_source: str = "llm_inference"
    effort_adjustment_factor: float = 1.0


class DockerfileImageFinding(BaseModel):
    dockerfile_path: str
    base_image: str
    tag: str = "latest"
    stage_name: Optional[str] = None
    status: AvailabilityStatus = AvailabilityStatus.NATIVE_AVAILABLE
    notes: Optional[str] = None
    effort_pd: float = 0.0


class ConfigImageFinding(BaseModel):
    config_file_path: str
    config_file_type: str = "compose"
    image_ref: str
    status: AvailabilityStatus = AvailabilityStatus.NATIVE_AVAILABLE
    notes: Optional[str] = None
    effort_pd: float = 0.0


class PackageTriageResult(BaseModel):
    package_name: str
    requested_version: Optional[str] = "latest"
    ecosystem: str = "container"
    status: AvailabilityStatus
    tier_description: str
    evidence_source: Optional[str] = None
    evidence_url: Optional[str] = None
    git_repo_url: Optional[str] = None
    doc_url: Optional[str] = None
    substitute_package: Optional[str] = None
    version_warning: Optional[str] = None

    # Deliverable-type aware support classification
    deliverable_match: DeliverableMatchStatus = DeliverableMatchStatus.SUPPORTED
    deliverable_detail: Optional[str] = None   # human-readable explanation of partial match

    # Deep build analysis
    build_system: Optional[str] = None
    toolchain_prerequisites: List[ToolchainRequirement] = Field(default_factory=list)
    build_dependencies: List[BuildDependency] = Field(default_factory=list)
    test_dependencies: List[TestDependency] = Field(default_factory=list)
    test_effort_pd: float = 0.0
    arch_sensitivity: Optional[ArchSensitivity] = None
    arch_support_scan: Optional[ArchSupportScan] = None
    dockerfile_image_findings: List[DockerfileImageFinding] = Field(default_factory=list)
    config_image_findings: List[ConfigImageFinding] = Field(default_factory=list)

    # Effort computation
    base_build_effort_pd: float = 0.0
    transitive_deps_effort_pd: float = 0.0
    base_arch_complexity_effort_pd: float = 0.0
    arch_complexity_effort_pd: float = 0.0
    total_effort_pd: int = 0
    confidence_level: str = "High"
    porting_notes: str = ""


class TriageSummary(BaseModel):
    total_packages: int
    native_count: int
    agnostic_count: int
    substitute_count: int
    unported_count: int
    blocker_count: int
    readiness_score_pct: float
    recommendation: SalesRecommendationTier
    recommendation_reason: str
    fibonacci_effort_pd: int = 0
    min_total_person_days: int = 0
    max_total_person_days: int = 0
    unported_transitive_deps_count: int
    test_deps_unresolved_count: int = 0
    partial_support_count: int = 0   # packages with PARTIAL_* deliverable match


class AgentStep(BaseModel):
    step_id: int
    agent_name: str
    action_type: str  # "plan", "lookup", "deep_scan", "llm_reasoning", "synthesis", "url_inference"
    target: str
    thought: str
    detail: Optional[str] = None
    status: str = "completed"


class TriageRequest(BaseModel):
    project_name: Optional[str] = "Customer Migration Triage"

    # Combined environment (preferred)
    target_environment: TargetEnvironment = TargetEnvironment.RHEL9_OCP

    # Legacy separate fields — kept for backwards compatibility but derived from
    # target_environment when not explicitly overridden.
    target_os: TargetOS = TargetOS.RHEL9
    target_platform: TargetPlatform = TargetPlatform.OPENSHIFT

    triage_depth: TriageDepth = TriageDepth.DEEP

    # Deliverable type the customer wants on Power
    deliverable_type: DeliverableType = DeliverableType.CONTAINER

    # Flexible input fields
    raw_manifest: Optional[str] = None
    manifest_type: Optional[str] = "auto"  # "sbom", "dockerfile", "requirements", "text", "auto", "url"
    git_repo_url: Optional[str] = None
    doc_url: Optional[str] = None
    packages_list: Optional[List[Dict[str, str]]] = None

    # LLM config override
    gemini_api_key: Optional[str] = None

    def effective_os(self) -> str:
        return self.target_environment.os

    def effective_platform(self) -> str:
        return self.target_environment.platform


class TriageResponse(BaseModel):
    project_name: str
    target_os: str
    target_platform: str
    target_environment: str = ""
    deliverable_type: str = "container"
    summary: TriageSummary
    packages: List[PackageTriageResult]
    agent_steps: List[AgentStep]
    executive_brief_markdown: str
    export_csv_data: Optional[str] = None
    primary_package_name: Optional[str] = None
    git_repo_url: Optional[str] = None
    doc_url: Optional[str] = None
    source_url: Optional[str] = None
    package_ecosystem: Optional[str] = None
    package_version: Optional[str] = None
