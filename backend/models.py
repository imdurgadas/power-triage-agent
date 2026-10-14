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


# v4: positive effort-oriented tiers (Porting Lifecycle WBS sizing)
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


class SizingBreakdown(BaseModel):
    prep_env_pd: float = 0.0               # Environment & Toolchain Preparation
    readiness_audit_pd: float = 0.0        # Architecture Readiness & Feasibility Inspection
    build_source_pd: float = 0.0           # Source Compilation & Core Porting
    ci_pipeline_pd: float = 0.0            # CI Pipeline & Multi-Arch Container Integration
    bug_fix_validation_pd: float = 0.0     # Testing, Bug Fixing & Stabilization
    contingency_buffer_pd: float = 0.0     # Risk & Upstream Contingency Buffer (20-25%)
    contingency_pct: float = 20.0          # Percentage buffer applied
    subtotal_pd: float = 0.0               # Subtotal effort before buffer
    total_estimated_pd: int = 0            # Total committed person-days
    methodology_note: str = ""


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
    estimated_effort_pd: int = 0
    min_total_person_days: int = 0
    max_total_person_days: int = 0
    unported_transitive_deps_count: int
    test_deps_unresolved_count: int = 0
    partial_support_count: int = 0   # packages with PARTIAL_* deliverable match
    sizing_breakdown: Optional[SizingBreakdown] = None
    token_usage: Optional['TokenUsage'] = None


class TokenStageBreakdown(BaseModel):
    stage: str
    calls_count: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    percentage: float = 0.0


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    llm_provider: str = "ibm_bob"
    llm_model: str = "bob-shell"
    calls_count: int = 0
    breakdown: List[TokenStageBreakdown] = Field(default_factory=list)


TriageSummary.model_rebuild()


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

    # Image input
    image_data_base64: Optional[str] = None
    image_media_type: Optional[str] = "image/png"

    # LLM config override
    llm_provider: Optional[str] = "ibm_bob"  # "ibm_bob" | "gemini" | "auto"
    bobshell_api_key: Optional[str] = None
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
    token_usage: Optional[TokenUsage] = None


class PowerVMConfig(BaseModel):
    """Configuration for connecting to or provisioning an IBM Power (ppc64le) target VM."""
    host: str = ""
    port: int = 22
    username: str = "root"
    private_key: Optional[str] = None
    password: Optional[str] = None
    use_mock: bool = False
    cloud_provider: str = "direct_ssh"  # "direct_ssh" | "powervs" | "openstack"
    workspace_dir: str = "/var/tmp/power_porting"
    target_os_image: str = "registry.access.redhat.com/ubi9/ubi:latest"
    container_engine: str = "auto"  # "auto" | "podman" | "docker"


class PortingActionType(str, Enum):
    BUILD_FROM_SOURCE = "build_from_source"
    BUILD_WHEEL       = "build_wheel"
    CREATE_CONTAINER  = "create_container"


class PortingPlan(BaseModel):
    """Structured plan specifying actions required to make a package available on ppc64le."""
    package_name: str
    version: str = "latest"
    ecosystem: str = "python"
    git_repo_url: Optional[str] = None
    deliverable_target: str = "wheel"  # "wheel" | "container" | "source"
    action_type: PortingActionType = PortingActionType.BUILD_WHEEL
    detected_sensitivities: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    build_commands: List[str] = Field(default_factory=list)
    test_commands: List[str] = Field(default_factory=list)
    rationale: str = ""


class PortingJobStep(BaseModel):
    step_number: int
    title: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed" | "skipped"
    detail: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class PortingJobRequest(BaseModel):
    package_name: str
    version: Optional[str] = "latest"
    ecosystem: Optional[str] = "python"
    git_repo_url: Optional[str] = None
    deliverable_target: Optional[str] = "wheel"  # "wheel" | "container" | "source"
    vm_config: PowerVMConfig
    github_token: Optional[str] = None
    upstream_repo: Optional[str] = None
    pr_target_branch: Optional[str] = "main"
    llm_provider: Optional[str] = "ibm_bob"  # "ibm_bob" | "gemini"
    triage_finding: Optional[Dict[str, Any]] = None
    include_child_dependencies: bool = True
    child_dependencies: List[Dict[str, Any]] = Field(default_factory=list)


class PortingJobResponse(BaseModel):
    job_id: str
    package_name: str
    version: str = "latest"
    status: str = "queued"  # "queued" | "running" | "completed" | "failed"
    current_step_index: int = 0
    steps: List[PortingJobStep] = Field(default_factory=list)
    vm_info: Dict[str, Any] = Field(default_factory=dict)
    container_info: Dict[str, Any] = Field(default_factory=dict)
    diff: Optional[str] = None
    files_modified: List[str] = Field(default_factory=list)
    test_summary: Dict[str, Any] = Field(default_factory=dict)
    artifact_path: Optional[str] = None
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    evidence_report_markdown: Optional[str] = None
    child_dependencies_ported: List[Dict[str, Any]] = Field(default_factory=list)
    token_usage: Optional[TokenUsage] = None
    error: Optional[str] = None


