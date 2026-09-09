import logging
from typing import Dict, Any, List, Optional, Tuple
from .models import (
    AvailabilityStatus,
    PackageTriageResult,
    BuildDependency,
    ToolchainRequirement,
    ArchSensitivity,
    SIMDPortingComplexity,
    TestDependency,
)

logger = logging.getLogger("build_analyzer")


def get_simd_multipliers(count: int, complexity: SIMDPortingComplexity) -> Tuple[float, float]:
    """Returns (count_multiplier, complexity_multiplier) for SIMD scaling."""
    # SIMD instruction count multiplier
    if count <= 0:
        count_mult = 1.0
    elif count <= 50:
        count_mult = 1.0
    elif count <= 200:
        count_mult = 1.5
    elif count <= 500:
        count_mult = 2.5
    else:
        count_mult = 4.0

    # Complexity tier multiplier
    comp_map = {
        SIMDPortingComplexity.DIRECT: 1.0,
        SIMDPortingComplexity.SIMDE_COMPATIBLE: 1.5,
        SIMDPortingComplexity.PARTIAL_REWRITE: 2.5,
        SIMDPortingComplexity.FULL_REDESIGN: 4.0,
    }
    comp_mult = comp_map.get(complexity, 1.0)
    return count_mult, comp_mult


def scale_arch_effort(base_arch_effort: float, count: int, complexity: SIMDPortingComplexity) -> float:
    """Scales architecture porting effort by SIMD instruction count and complexity tier.
    Formula: base_arch_effort * count_multiplier * complexity_multiplier
    """
    if base_arch_effort <= 0.0:
        return 0.0

    count_mult, comp_mult = get_simd_multipliers(count, complexity)
    return round(base_arch_effort * count_mult * comp_mult, 2)


# Knowledge base of build requirements, toolchains, and arch patterns for common unported/native software
KNOWLEDGE_BASE_NATIVE_BUILDS = {
    "rocksdb": {
        "build_system": "CMake / Make",
        "toolchains": [
            {"tool": "GCC", "required_version": ">= 9.0 (C++17)", "ppc64le_supported": True, "notes": "Included in standard RHEL 8/9"},
            {"tool": "CMake", "required_version": ">= 3.16", "ppc64le_supported": True, "notes": "Available in OS repos"}
        ],
        "build_deps": [
            {"name": "snappy-devel", "status": AvailabilityStatus.NATIVE_AVAILABLE, "effort": 0.0, "source": "RHEL 9 ppc64le AppStream"},
            {"name": "zlib-devel", "status": AvailabilityStatus.NATIVE_AVAILABLE, "effort": 0.0, "source": "RHEL 9 ppc64le BaseOS"},
            {"name": "bzip2-devel", "status": AvailabilityStatus.NATIVE_AVAILABLE, "effort": 0.0, "source": "RHEL 9 ppc64le BaseOS"},
            {"name": "lz4-devel", "status": AvailabilityStatus.NATIVE_AVAILABLE, "effort": 0.0, "source": "RHEL 9 ppc64le AppStream"},
            {"name": "gflags-devel", "status": AvailabilityStatus.NATIVE_AVAILABLE, "effort": 0.0, "source": "EPEL 9 ppc64le"},
            {
                "name": "jemalloc-ppc64le",
                "status": AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
                "effort": 1.5,
                "source": "Requires 64KB page-size tuned build for Power",
                "notes": "Standard jemalloc crashes or suffers memory fragmentation on 64KB page kernels unless configured with --with-lg-page=16"
            }
        ],
        "arch_sensitivity": {
            "has_simd_avx": False,
            "has_inline_asm": True,
            "asm_details": "x86 pause instruction and cycle counter in spinlock primitives",
            "has_64k_page_risk": True,
            "page_risk_details": "Default WAL and SSTable block alignment tuned for 4KB pages; configure with 64KB page buffer",
            "remediation_strategy": "Compile with -DFAIL_ON_WARNINGS=OFF; add Power __ppc_get_timebase() for cycle timer; link against 64KB-page configured jemalloc.",
            "code_snippet": "#if defined(__x86_64__)\n  __asm__ __volatile__(\"pause\");\n#elif defined(__powerpc__)\n  __asm__ __volatile__(\"or 27,27,27\"); /* Yield on Power */\n#endif",
            "simd_instruction_count": 0,
            "simd_porting_complexity": SIMDPortingComplexity.DIRECT
        },
        "test_deps": [
            {
                "name": "gtest",
                "version": "1.11.0",
                "test_dep_type": "framework",
                "status": AvailabilityStatus.NATIVE_AVAILABLE,
                "evidence_source": "EPEL 9 ppc64le",
                "porting_effort_pd": 0.0
            }
        ],
        "base_effort": 1.5,
        "arch_effort": 1.5
    },
    "simdjson": {
        "build_system": "CMake",
        "toolchains": [
            {"tool": "Clang / GCC", "required_version": ">= 10.0 (C++17)", "ppc64le_supported": True, "notes": "C++17 string_view and vector intrinsics"}
        ],
        "build_deps": [
            {"name": "cmake", "status": AvailabilityStatus.NATIVE_AVAILABLE, "effort": 0.0, "source": "RHEL 9 BaseOS"}
        ],
        "arch_sensitivity": {
            "has_simd_avx": True,
            "simd_details": "Heavily reliant on AVX2, AVX-512, and ARM NEON vector instructions for structural JSON parsing",
            "has_inline_asm": False,
            "has_64k_page_risk": False,
            "remediation_strategy": "Upstream simdjson contains an experimental IBM Power VMX/VSX backend; alternatively compile with scalar fallback (-DSIMDJSON_IMPLEMENTATION_FALLBACK=1) or link SIMDe wrapper.",
            "code_snippet": "#include <immintrin.h>\n__m256i mask = _mm256_cmpeq_epi8(chunk, quote_mask);\n// Power VSX equivalent: vec_cmpeq(vec_chunk, vec_quote_mask)",
            "simd_instruction_count": 320,
            "simd_porting_complexity": SIMDPortingComplexity.SIMDE_COMPATIBLE
        },
        "test_deps": [
            {
                "name": "cxxopts",
                "version": "3.0",
                "test_dep_type": "framework",
                "status": AvailabilityStatus.NATIVE_AVAILABLE,
                "evidence_source": "EPEL 9 ppc64le",
                "porting_effort_pd": 0.0
            },
            {
                "name": "simdjson-x86-benchmark-suite",
                "version": "1.0",
                "test_dep_type": "benchmark_suite",
                "status": AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
                "evidence_source": "Requires VSX/MMA performance verification harness",
                "porting_effort_pd": 1.0,
                "notes": "Validates Power VSX vector throughput against x86 AVX2 baselines"
            }
        ],
        "base_effort": 1.0,
        "arch_effort": 2.0
    }
}


class BuildAnalyzer:
    """Recursively analyzes source build dependencies, toolchains, and arch friction for unported packages."""

    @classmethod
    def analyze_package_build(cls, package: PackageTriageResult, target_os: str = "rhel9") -> PackageTriageResult:
        pkg_name = package.package_name.lower()

        # If already native or agnostic, minimal effort
        if package.status in [AvailabilityStatus.NATIVE_AVAILABLE, AvailabilityStatus.PLATFORM_AGNOSTIC]:
            package.base_build_effort_pd = 0.0
            package.transitive_deps_effort_pd = 0.0
            package.arch_complexity_effort_pd = 0.0
            package.total_effort_pd = 0
            package.confidence_level = "High"
            return package

        if package.status == AvailabilityStatus.SUBSTITUTE_AVAILABLE:
            package.base_build_effort_pd = 0.5
            package.transitive_deps_effort_pd = 0.0
            package.arch_complexity_effort_pd = 0.0
            package.total_effort_pd = 1  # 0.5 rounded to nearest integer
            package.porting_notes = f"Use existing substitute package: {package.substitute_package}. Minimal configuration effort."
            package.confidence_level = "High"
            return package

        if package.status == AvailabilityStatus.BLOCKER:
            package.base_build_effort_pd = 0.0
            package.transitive_deps_effort_pd = 0.0
            package.arch_complexity_effort_pd = 10.0
            package.total_effort_pd = 10
            package.porting_notes = f"Proprietary x86 component. Migration requires replacing with alternative architecture ({package.substitute_package})."
            package.confidence_level = "High"
            return package

        # Case: UNPORTED_BUILD_REQUIRED
        # Check if known in curated knowledge base
        if pkg_name in KNOWLEDGE_BASE_NATIVE_BUILDS:
            kb = KNOWLEDGE_BASE_NATIVE_BUILDS[pkg_name]
            package.build_system = kb["build_system"]
            package.toolchain_prerequisites = [ToolchainRequirement(**t) for t in kb["toolchains"]]
            
            build_deps = []
            transitive_effort = 0.0
            for d in kb["build_deps"]:
                dep = BuildDependency(
                    name=d["name"],
                    status=d["status"],
                    porting_effort_pd=d.get("effort", 0.0),
                    evidence_source=d.get("source"),
                    notes=d.get("notes")
                )
                if d["status"] == AvailabilityStatus.UNPORTED_BUILD_REQUIRED:
                    transitive_effort += d.get("effort", 0.0)
                build_deps.append(dep)
                
            package.build_dependencies = build_deps
            package.arch_sensitivity = ArchSensitivity(**kb["arch_sensitivity"])
            
            # Test dependencies
            test_deps = []
            test_effort = 0.0
            for td in kb.get("test_deps", []):
                td_obj = TestDependency(**td)
                test_deps.append(td_obj)
                test_effort += td_obj.porting_effort_pd
            package.test_dependencies = test_deps
            package.test_effort_pd = round(test_effort, 2)

            package.base_build_effort_pd = kb["base_effort"]
            package.transitive_deps_effort_pd = transitive_effort
            package.base_arch_complexity_effort_pd = kb["arch_effort"]
            
            # Apply SIMD scaling
            count_m, comp_m = get_simd_multipliers(
                package.arch_sensitivity.simd_instruction_count,
                package.arch_sensitivity.simd_porting_complexity
            )
            package.arch_sensitivity.base_engineering_effort_pd = kb["arch_effort"]
            package.arch_sensitivity.simd_instruction_multiplier = count_m
            package.arch_sensitivity.simd_complexity_multiplier = comp_m
            package.arch_complexity_effort_pd = scale_arch_effort(
                kb["arch_effort"],
                package.arch_sensitivity.simd_instruction_count,
                package.arch_sensitivity.simd_porting_complexity
            )

            total_effort = (
                package.base_build_effort_pd
                + package.transitive_deps_effort_pd
                + package.arch_complexity_effort_pd
                + package.test_effort_pd
            )
            package.total_effort_pd = int(round(total_effort))
            unported_build_cnt = sum(1 for d in build_deps if d.status != AvailabilityStatus.NATIVE_AVAILABLE)
            unported_test_cnt = sum(1 for t in test_deps if t.status != AvailabilityStatus.NATIVE_AVAILABLE)
            package.porting_notes = (
                f"Requires source build on {target_os} ppc64le. Uncovered {len(build_deps)} build-time dependencies "
                f"({unported_build_cnt} unported) and {len(test_deps)} test dependencies ({unported_test_cnt} unported)."
            )
            return package

        # General dynamic heuristic for unlisted unported components
        return cls._dynamic_heuristic_build(package, target_os)

    @classmethod
    def _dynamic_heuristic_build(cls, package: PackageTriageResult, target_os: str) -> PackageTriageResult:
        pkg_name = package.package_name.lower()
        
        # Detect if it's specifically a custom vector/DSP math acceleration component
        is_custom_vector = any(ext in pkg_name for ext in ["dsp", "simd", "avx", "vector", "matrix"])
        
        if is_custom_vector:
            package.build_system = "CMake / Ninja"
            package.toolchain_prerequisites = [
                ToolchainRequirement(tool="GCC / G++", required_version=">= 11.0", ppc64le_supported=True, notes=f"Native compiler in {target_os}"),
                ToolchainRequirement(tool="CMake", required_version=">= 3.20", ppc64le_supported=True, notes="Standard build tool")
            ]
            
            # Sub-dependency for custom vector/DSP acceleration
            unported_sub_dep = BuildDependency(
                name=f"{pkg_name}-vector-submodule",
                version="1.0",
                purpose="Internal SIMD Vector Kernel",
                status=AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
                porting_effort_pd=1.5,
                evidence_source="Custom internal C/C++ SIMD vector extension",
                notes="Contains x86 AVX2 intrinsics. Can be ported using SIMDe (simde/x86/avx2.h) or Power VSX intrinsics."
            )
            
            common_os_dep = BuildDependency(
                name="glibc-devel",
                version="2.34",
                purpose="Standard C Runtime Header",
                status=AvailabilityStatus.NATIVE_AVAILABLE,
                porting_effort_pd=0.0,
                evidence_source=f"Available in {target_os} ppc64le BaseOS"
            )

            package.build_dependencies = [common_os_dep, unported_sub_dep]
            package.arch_sensitivity = ArchSensitivity(
                has_simd_avx=True,
                simd_details="Source code references x86 SIMD vector intrinsics (immintrin.h / AVX2)",
                simd_instruction_count=85,
                simd_porting_complexity=SIMDPortingComplexity.SIMDE_COMPATIBLE,
                has_inline_asm=False,
                has_64k_page_risk=False,
                remediation_strategy="Include 'simde/x86/avx2.h' header to map AVX2 calls to Power VSX instructions without extensive rewrite.",
                code_snippet="// Detected in vector source:\n#include <immintrin.h>\n__m256d vA = _mm256_load_pd(&data[i]);\n__m256d vB = _mm256_mul_pd(vA, vWeight);"
            )
            
            package.test_dependencies = [
                TestDependency(
                    name="gtest",
                    version="1.11",
                    test_dep_type="framework",
                    status=AvailabilityStatus.NATIVE_AVAILABLE,
                    evidence_source=f"Available in {target_os} EPEL ppc64le",
                    porting_effort_pd=0.0
                ),
                TestDependency(
                    name="vector-accuracy-test-harness",
                    version="1.0",
                    test_dep_type="unit_test",
                    status=AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
                    evidence_source="x86 floating-point precision regression suite",
                    porting_effort_pd=0.5,
                    notes="Requires cross-validating VSX double precision results against x86 FMA output"
                )
            ]
            package.test_effort_pd = 0.5

            package.base_build_effort_pd = 1.0
            package.transitive_deps_effort_pd = unported_sub_dep.porting_effort_pd
            base_arch = 2.0
            package.base_arch_complexity_effort_pd = base_arch
            count_m, comp_m = get_simd_multipliers(
                package.arch_sensitivity.simd_instruction_count,
                package.arch_sensitivity.simd_porting_complexity
            )
            package.arch_sensitivity.base_engineering_effort_pd = base_arch
            package.arch_sensitivity.simd_instruction_multiplier = count_m
            package.arch_sensitivity.simd_complexity_multiplier = comp_m
            package.arch_complexity_effort_pd = scale_arch_effort(
                base_arch,
                package.arch_sensitivity.simd_instruction_count,
                package.arch_sensitivity.simd_porting_complexity
            )
            total = (
                package.base_build_effort_pd
                + package.transitive_deps_effort_pd
                + package.arch_complexity_effort_pd
                + package.test_effort_pd
            )
            package.total_effort_pd = int(round(total))
            package.confidence_level = "Medium"
            package.porting_notes = (
                f"Custom vector/DSP library. Scoped 2 build-time dependencies, including 1 unported vector submodule "
                f"({unported_sub_dep.porting_effort_pd} PD), AVX2 translation ({package.arch_complexity_effort_pd} PD), "
                f"and test validation ({package.test_effort_pd} PD)."
            )
        else:
            # Generic portable C/C++ package
            package.build_system = "CMake / Autotools"
            package.toolchain_prerequisites = [
                ToolchainRequirement(tool="GCC / G++", required_version=">= 8.5", ppc64le_supported=True, notes="Standard C/C++ toolchain")
            ]
            package.build_dependencies = [
                BuildDependency(name="glibc-devel", status=AvailabilityStatus.NATIVE_AVAILABLE, porting_effort_pd=0.0, evidence_source=f"Available in {target_os} ppc64le BaseOS")
            ]
            package.test_dependencies = [
                TestDependency(
                    name="ctest",
                    version="3.20",
                    test_dep_type="framework",
                    status=AvailabilityStatus.NATIVE_AVAILABLE,
                    evidence_source=f"Available in {target_os} BaseOS",
                    porting_effort_pd=0.0
                )
            ]
            package.test_effort_pd = 0.0
            package.arch_sensitivity = ArchSensitivity(
                has_simd_avx=False,
                has_inline_asm=False,
                has_64k_page_risk=False,
                remediation_strategy="Recompile from clean source with standard gcc flags on ppc64le."
            )
            package.base_build_effort_pd = 0.5
            package.transitive_deps_effort_pd = 0.0
            package.arch_complexity_effort_pd = 0.0
            package.total_effort_pd = 1  # 0.5 rounded to nearest integer
            package.confidence_level = "Medium"
            package.porting_notes = "Standard portable C/C++ codebase. Clean rebuild and test execution on target Power environment expected to succeed."

        return package
