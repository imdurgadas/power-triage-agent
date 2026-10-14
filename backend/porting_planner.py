"""
porting_planner.py
Analyzes triage findings and package characteristics to formulate a concrete,
reproducible porting plan on IBM Power (ppc64le).
"""

import logging
from typing import Dict, Any, Optional, List

from .models import (
    PortingPlan,
    PortingActionType,
    PackageTriageResult,
    AvailabilityStatus,
    SIMDPortingComplexity,
)

logger = logging.getLogger("porting_planner")


def formulate_porting_plan(
    package_name: str,
    version: str = "latest",
    ecosystem: str = "python",
    deliverable_target: str = "wheel",
    git_repo_url: Optional[str] = None,
    triage_finding: Optional[Dict[str, Any]] = None,
) -> PortingPlan:
    """Formulates a step-by-step porting execution plan from triage findings."""

    pkg = package_name.lower().strip()
    ver = version or "latest"
    eco = (ecosystem or "python").lower()
    deliv = (deliverable_target or "wheel").lower()

    # Extract sensitivity markers from triage finding if available
    sensitivities: List[str] = []
    prereqs: List[str] = ["gcc", "gcc-c++", "make", "git"]
    build_cmds: List[str] = []
    test_cmds: List[str] = []
    action_type = PortingActionType.BUILD_WHEEL
    rationale_parts: List[str] = []

    repo_url = git_repo_url
    if not repo_url and triage_finding:
        repo_url = triage_finding.get("git_repo_url") or triage_finding.get("url")

    # If git repo is still not provided, synthesize standard upstream repository URL
    if not repo_url:
        if eco == "python":
            repo_url = f"https://github.com/{pkg}/{pkg}"
        else:
            repo_url = f"https://github.com/upstream/{pkg}"

    # Analyze triage finding arch sensitivity
    arch_sens = triage_finding.get("arch_sensitivity") if triage_finding else None
    if isinstance(arch_sens, dict):
        if arch_sens.get("has_simd_avx"):
            sensitivities.append("x86 SIMD / AVX2 intrinsics in hot path requiring VSX or SIMDe mapping")
            prereqs.append("simde-devel")
        if arch_sens.get("has_64k_page_risk"):
            sensitivities.append("64KB memory page size compatibility risk (Power Linux default is 64KB)")
        if arch_sens.get("has_endianness_risk"):
            sensitivities.append("Potential byte-ordering / endianness assumptions")
        if arch_sens.get("has_inline_asm"):
            sensitivities.append("x86 inline assembly requiring Power PPC64 inline assembly or C fallback")
    else:
        # Dynamic check based on ecosystem and deliverable without hardcoded package names
        if eco in ("native_c", "c_cpp", "cpp", "c") or deliv in ("source", "build"):
            sensitivities.append("Native C/C++ architecture inspection required for ppc64le vectorization & 64KB page support")
            prereqs.append("simde-devel")

    # Determine Deliverable Target & Strategy
    if deliv in ("container", "docker"):
        action_type = PortingActionType.CREATE_CONTAINER
        prereqs.extend(["podman", "buildah"])
        build_cmds = [
            f"podman build --arch ppc64le -t {pkg}:{ver}-ppc64le -f Dockerfile .",
            f"podman images | grep {pkg}",
        ]
        test_cmds = [
            f"podman run --rm {pkg}:{ver}-ppc64le {pkg} --version || podman run --rm {pkg}:{ver}-ppc64le pytest -v",
        ]
        rationale_parts.append(
            f"Containerized workload requested: building ppc64le native container image with multi-arch manifest tag."
        )

    elif deliv in ("source", "build", "rpm", "binary", "c_cpp", "cpp"):
        action_type = PortingActionType.BUILD_FROM_SOURCE
        prereqs.extend(["cmake", "ninja-build"])
        build_cmds = [
            "cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS='-mcpu=power9 -mtune=power10' -DCMAKE_CXX_FLAGS='-mcpu=power9 -mtune=power10'",
            "cmake --build build -j$(nproc)",
        ]
        test_cmds = [
            "ctest --test-dir build --output-on-failure",
        ]
        rationale_parts.append(
            f"Native binary / source build deliverable: compiling C/C++ project with Power9/Power10 optimization flags."
        )

    else:
        action_type = PortingActionType.BUILD_WHEEL
        prereqs.extend(["python3-devel", "python3-pip", "python3-wheel", "cmake"])
        build_cmds = [
            "python3 -m pip install --upgrade pip build wheel setuptools",
            "CFLAGS='-mcpu=power9 -mtune=power10 -O3 -maltivec -mvsx' python3 -m build --wheel --no-isolation",
            "ls -la dist/*.whl",
        ]
        test_cmds = [
            "python3 -m pip install dist/*.whl pytest",
            "pytest -v tests/",
        ]
        rationale_parts.append(
            f"Python C-extension/wheel deliverable required: compiling native ppc64le wheel with Power VSX optimization."
        )

    if sensitivities:
        rationale_parts.append(
            f"Remediation required for: {'; '.join(sensitivities)}. All code modifications must strictly isolate ppc64le logic with '#if defined(__powerpc__) || defined(__PPC64__)' without affecting x86_64 or aarch64 code paths."
        )
    else:
        rationale_parts.append(
            "Standard compile and test cycle on ppc64le with upstream PR verification evidence."
        )

    return PortingPlan(
        package_name=pkg,
        version=ver,
        ecosystem=eco,
        git_repo_url=repo_url,
        deliverable_target=deliv,
        action_type=action_type,
        detected_sensitivities=sensitivities,
        prerequisites=list(dict.fromkeys(prereqs)),
        build_commands=build_cmds,
        test_commands=test_cmds,
        rationale=" ".join(rationale_parts),
    )
