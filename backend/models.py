from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TargetOS(str, Enum):
    RHEL8 = "rhel8"
    RHEL9 = "rhel9"
    UBUNTU22 = "ubuntu22"
    UBUNTU24 = "ubuntu24"
    SLES15 = "sles15"


class TargetPlatform(str, Enum):
    BARE_METAL = "baremetal"
    POWER_VM = "powervm"
    OPENSHIFT = "ocp"


class TriageDepth(str, Enum):
    EXPRESS = "express"
    DEEP = "deep"


class AvailabilityStatus(str, Enum):
    NATIVE_AVAILABLE = "native_available"
    PLATFORM_AGNOSTIC = "platform_agnostic"
    SUBSTITUTE_AVAILABLE = "substitute_available"
    UNPORTED_BUILD_REQUIRED = "unported_build_required"
    BLOCKER = "blocker"


class RecommendationTrafficLight(str, Enum):
    GO = "GO"
    CAUTION = "CAUTION"
    HIGH_RISK = "HIGH_RISK"


class SIMDPortingComplexity(str, Enum):
    DIRECT = "DIRECT"
    SIMDE_COMPATIBLE = "SIMDE_COMPATIBLE"
    PARTIAL_REWRITE = "PARTIAL_REWRITE"
    FULL_REDESIGN = "FULL_REDESIGN"


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
    tool: str  # e.g., "Bazel", "GCC", "LLVM/Clang", "Rust", "CMake"
    required_version: str
    ppc64le_supported: bool = True
    notes: Optional[str] = None


class BuildDependency(BaseModel):
    name: str
    version: Optional[str] = None
    purpose: str = "BuildRequires"  # e.g. "BuildRequires", "LinkHeader", "NativeExtension"
    status: AvailabilityStatus = AvailabilityStatus.NATIVE_AVAILABLE
    evidence_source: Optional[str] = None
    porting_effort_pd: float = 0.0
    notes: Optional[str] = None
    transitive_children: List["BuildDependency"] = Field(default_factory=list)


class TestDependency(BaseModel):
    __test__ = False
    name: str
    version: Optional[str] = None
    test_dep_type: str = "framework"  # "framework", "runtime_container", "native_lib"
    status: AvailabilityStatus = AvailabilityStatus.NATIVE_AVAILABLE
    evidence_source: Optional[str] = None
    porting_effort_pd: float = 0.0
    notes: Optional[str] = None


class ArchSupportScan(BaseModel):
    ppc64le_markers_found: List[str] = Field(default_factory=list)
    x86_only_markers_found: List[str] = Field(default_factory=list)
    ci_matrix_has_power: bool = False
    scan_source: str = "llm_inference"  # "repo_clone" or "llm_inference"
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
    config_file_type: str = "compose"  # "compose", "github_workflow", "k8s_manifest", "helm_values"
    image_ref: str
    status: AvailabilityStatus = AvailabilityStatus.NATIVE_AVAILABLE
    notes: Optional[str] = None
    effort_pd: float = 0.0


class PackageTriageResult(BaseModel):
    package_name: str
    requested_version: Optional[str] = "latest"
    ecosystem: str = "container"  # "container", "pypi", "rpm", "npm", "maven", "native_c"
    status: AvailabilityStatus
    tier_description: str
    evidence_source: Optional[str] = None
    evidence_url: Optional[str] = None
    substitute_package: Optional[str] = None
    version_warning: Optional[str] = None
    
    # Deep build analysis
    build_system: Optional[str] = None  # "CMake", "Make", "setup.py", "Bazel", "Cargo", "None"
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
    confidence_level: str = "High"  # "High", "Medium", "Estimated"
    porting_notes: str = ""


class TriageSummary(BaseModel):
    total_packages: int
    native_count: int
    agnostic_count: int
    substitute_count: int
    unported_count: int
    blocker_count: int
    readiness_score_pct: float
    recommendation: RecommendationTrafficLight
    recommendation_reason: str
    min_total_person_days: int
    max_total_person_days: int
    unported_transitive_deps_count: int
    test_deps_unresolved_count: int = 0


class AgentStep(BaseModel):
    step_id: int
    agent_name: str
    action_type: str  # "plan", "lookup", "deep_scan", "llm_reasoning", "synthesis"
    target: str
    thought: str
    detail: Optional[str] = None
    status: str = "completed"  # "running", "completed", "warning"


class TriageRequest(BaseModel):
    project_name: Optional[str] = "Customer Migration Triage"
    target_os: TargetOS = TargetOS.RHEL9
    target_platform: TargetPlatform = TargetPlatform.OPENSHIFT
    triage_depth: TriageDepth = TriageDepth.DEEP
    
    # Flexible input fields
    raw_manifest: Optional[str] = None
    manifest_type: Optional[str] = "auto"  # "sbom", "dockerfile", "requirements", "text", "auto"
    git_repo_url: Optional[str] = None
    packages_list: Optional[List[Dict[str, str]]] = None
    
    # LLM config override (optional)
    gemini_api_key: Optional[str] = None


class TriageResponse(BaseModel):
    project_name: str
    target_os: str
    target_platform: str
    summary: TriageSummary
    packages: List[PackageTriageResult]
    agent_steps: List[AgentStep]
    executive_brief_markdown: str
    export_csv_data: Optional[str] = None
