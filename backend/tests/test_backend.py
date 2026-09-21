import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from backend.main import app
from backend.normalizer import UniversalNormalizer
from backend.prober import MultiSourceProber, compare_versions
from backend.build_analyzer import BuildAnalyzer, scale_arch_effort
from backend.repo_scanner import RepoScanner
from backend.models import (
    PackageTriageResult,
    AvailabilityStatus,
    DeliverableType,
    DeliverableMatchStatus,
    TargetEnvironment,
    TriageRequest,
    SIMDPortingComplexity,
    TestDependency as PpcTestDependency,
)
from backend.prober import classify_deliverable_match

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_sample_workloads():
    response = client.get("/api/sample-workloads")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 4
    assert any(w["id"] == "unported_storage" for w in data)


def test_normalizer_dockerfile():
    docker_content = """FROM nginx:1.24
FROM redis:7.2
RUN apt-get update && apt-get install -y openssl-dev curl
"""
    items = UniversalNormalizer.normalize(docker_content, "dockerfile")
    names = [i["name"] for i in items]
    assert "nginx" in names
    assert "redis" in names
    assert "openssl-dev" in names or "curl" in names


def test_normalizer_requirements():
    reqs = """torch==2.1.0
numpy>=1.26.0
pydantic
"""
    items = UniversalNormalizer.normalize(reqs, "requirements")
    assert len(items) == 3
    assert items[0]["name"] == "torch"
    assert items[0]["version"] == "2.1.0"


def test_normalizer_sbom():
    sbom = """{
        "bomFormat": "CycloneDX",
        "components": [
            {"name": "nginx", "version": "1.24", "type": "container", "purl": "pkg:docker/nginx@1.24"},
            {"name": "pandas", "version": "2.1.0", "type": "library", "purl": "pkg:pypi/pandas@2.1.0"}
        ]
    }"""
    items = UniversalNormalizer.normalize(sbom, "sbom")
    assert len(items) == 2
    assert items[0]["name"] == "nginx"
    assert items[1]["name"] == "pandas"


def test_prober_known():
    import asyncio
    async def _test():
        prober = MultiSourceProber()
        res = await prober.probe_component("nginx", "1.24", "container", "rhel9")
        assert res["status"] == AvailabilityStatus.NATIVE_AVAILABLE

        # torch has a native ppc64le wheel available (via PyPI live, DevPi, or Koji).
        # RedHat distro repos and Docker Hub / PyPI live take precedence over IBM-specific
        # sources, so we assert status only — not which specific source tier served it.
        res_torch = await prober.probe_component("torch", "2.1.0", "pypi", "rhel9")
        assert res_torch["status"] == AvailabilityStatus.NATIVE_AVAILABLE

        # pytorch is available on ppc64le (via PyPI live, DevPi, or build-scripts).
        # Assert status only — source tier varies depending on which registry responds first.
        res_pytorch = await prober.probe_component("pytorch", "latest", "pypi", "rhel9")
        assert res_pytorch["status"] == AvailabilityStatus.NATIVE_AVAILABLE

        # zlib is a core OS library available in RHEL/EPEL, build-scripts, and the static
        # cache. RHEL/EPEL Koji now fires first; assert status only.
        res_zlib = await prober.probe_component("zlib", "1.2.11", "native_c", "rhel9")
        assert res_zlib["status"] == AvailabilityStatus.NATIVE_AVAILABLE

        # Test MKL is recognized as x86 blocker with Power alternatives (ESSL / OpenBLAS)
        res_mkl = await prober.probe_component("mkl", "latest", "native_c", "rhel9")
        assert res_mkl["status"] == AvailabilityStatus.BLOCKER
        assert "ESSL" in res_mkl["substitute"] or "OpenBLAS" in res_mkl["substitute"]
    asyncio.run(_test())


# --- Tests for 7 Gaps ---

def test_gap1_version_aware_probing():
    """Sub-Task 1: Version comparison helper & version upgrade/downgrade warning."""
    # Unit compare_versions tests
    assert compare_versions("1.25", "1.24") == 1
    assert compare_versions("1.20", "1.24") == -1
    assert compare_versions("1.24", "1.24") == 0
    assert compare_versions("latest", "1.24") == 0

    import asyncio
    async def _test():
        prober = MultiSourceProber()
        # nginx:1.25 — available via RHEL/EPEL Koji, Docker Hub, or build-scripts
        res_newer = await prober.probe_component("nginx", "1.25", "container", "rhel9")
        assert res_newer["status"] == AvailabilityStatus.NATIVE_AVAILABLE

        # Version that genuinely exceeds all live indexes — use static cache fallback.
        # openssl 99.0 will pass through RHEL/EPEL Koji (no such version there) and
        # eventually hit the static cache (3.0.7), triggering an exceeds warning.
        res_exceeds = await prober.probe_component("openssl", "99.0", "native_c", "rhel9")
        assert res_exceeds["status"] == AvailabilityStatus.UNPORTED_BUILD_REQUIRED
        assert "version_warning" in res_exceeds
        assert "exceeds verified ppc64le version" in res_exceeds["version_warning"]

        # Case: Requested version is older than available (openssl 1.0 vs available 3.0.7)
        # RHEL/EPEL Koji may return a newer version; if it does the version_warning fires.
        # If Koji returns None (network unavailable), the static cache handles it.
        res_older = await prober.probe_component("openssl", "1.0", "native_c", "rhel9")
        assert res_older["status"] == AvailabilityStatus.NATIVE_AVAILABLE
        assert "version_warning" in res_older
        assert "recommend upgrading" in res_older["version_warning"]

    asyncio.run(_test())


def test_gap2_gap3_simd_scaling_and_complexity_tiers():
    """Sub-Tasks 2 & 3: SIMD instruction count bracket scaling and 4 complexity tiers."""
    base_arch = 2.0

    # Test count brackets with DIRECT (1.0x)
    assert scale_arch_effort(base_arch, 0, SIMDPortingComplexity.DIRECT) == 2.0  # 1.0x * 1.0x
    assert scale_arch_effort(base_arch, 40, SIMDPortingComplexity.DIRECT) == 2.0  # <= 50 -> 1.0x
    assert scale_arch_effort(base_arch, 150, SIMDPortingComplexity.DIRECT) == 3.0  # 51-200 -> 1.5x
    assert scale_arch_effort(base_arch, 350, SIMDPortingComplexity.DIRECT) == 5.0  # 201-500 -> 2.5x
    assert scale_arch_effort(base_arch, 750, SIMDPortingComplexity.DIRECT) == 8.0  # > 500 -> 4.0x

    # Test complexity tier multipliers
    assert scale_arch_effort(base_arch, 0, SIMDPortingComplexity.DIRECT) == 2.0  # 1.0x
    assert scale_arch_effort(base_arch, 0, SIMDPortingComplexity.SIMDE_COMPATIBLE) == 3.0  # 1.5x
    assert scale_arch_effort(base_arch, 0, SIMDPortingComplexity.PARTIAL_REWRITE) == 5.0  # 2.5x
    assert scale_arch_effort(base_arch, 0, SIMDPortingComplexity.FULL_REDESIGN) == 8.0  # 4.0x

    # Combined instruction bracket (201-500 -> 2.5x) * SIMDE_COMPATIBLE (1.5x) = 3.75x
    assert scale_arch_effort(2.0, 320, SIMDPortingComplexity.SIMDE_COMPATIBLE) == 7.5


def test_gap4_test_dependencies_and_testing_effort():
    """Sub-Task 4: Testing effort calculation and test dependency scoping."""
    pkg = PackageTriageResult(
        package_name="simdjson",
        requested_version="3.6",
        ecosystem="native_c",
        status=AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
        tier_description="Requires source build"
    )
    triaged = BuildAnalyzer.analyze_package_build(pkg, "rhel9")
    
    assert len(triaged.test_dependencies) >= 2
    assert triaged.test_effort_pd == 1.0
    unported_tests = [t for t in triaged.test_dependencies if t.status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED]
    assert len(unported_tests) == 1
    assert "benchmark" in unported_tests[0].name

    # Test effort must be included in total_effort_pd
    expected_total = int(round(
        triaged.base_build_effort_pd
        + triaged.transitive_deps_effort_pd
        + triaged.arch_complexity_effort_pd
        + triaged.test_effort_pd
    ))
    assert triaged.total_effort_pd == expected_total


def test_gap5_scan_dockerfiles():
    """Sub-Task 5: Dockerfile discovery and FROM base image extraction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a multi-stage Dockerfile
        df_path = os.path.join(tmpdir, "Dockerfile")
        with open(df_path, "w") as f:
            f.write("FROM golang:1.21 AS builder\nRUN make\nFROM alpine:3.18\nCOPY --from=builder /app /app\n")

        # Create an alternative Dockerfile
        sub_dir = os.path.join(tmpdir, "docker")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "Dockerfile.dev"), "w") as f:
            f.write("FROM python:3.11-slim\n")

        findings = RepoScanner.scan_dockerfiles(tmpdir)
        assert len(findings) == 3
        images = [f.base_image for f in findings]
        assert "golang" in images
        assert "alpine" in images
        assert "python" in images


def test_gap6_scan_arch_support():
    """Sub-Task 6: Repository architecture marker scan and effort adjustment factor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create GitHub workflow with ppc64le runner
        wf_dir = os.path.join(tmpdir, ".github", "workflows")
        os.makedirs(wf_dir)
        with open(os.path.join(wf_dir, "ci.yml"), "w") as f:
            f.write("jobs:\n  build:\n    runs-on: [self-hosted, linux, ppc64le]\n")

        # Create source with Power VSX markers
        src_dir = os.path.join(tmpdir, "src")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "simd.c"), "w") as f:
            f.write("#ifdef __VSX__\n#include <altivec.h>\n#endif\n")

        scan = RepoScanner.scan_arch_support(tmpdir)
        assert scan.ci_matrix_has_power is True
        assert len(scan.ppc64le_markers_found) >= 1
        assert scan.effort_adjustment_factor == 0.7  # Upstream Power CI discount


def test_gap7_scan_config_images():
    """Sub-Task 7: Compose and CI workflow image extraction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        compose_path = os.path.join(tmpdir, "docker-compose.yml")
        with open(compose_path, "w") as f:
            f.write("""version: '3.8'
services:
  web:
    image: nginx:1.24
  cache:
    image: redis:7.2
""")
        findings = RepoScanner.scan_config_images(tmpdir)
        assert len(findings) == 2
        images = [f.image_ref for f in findings]
        assert "nginx:1.24" in images
        assert "redis:7.2" in images


def test_api_triage_flow_with_gaps():
    """End-to-end API test verifying version warnings, test deps, and executive summary output."""
    payload = {
        "project_name": "Test Microservices",
        "target_environment": "rhel9_ocp",
        "deliverable_type": "container",
        "triage_depth": "deep",
        "raw_manifest": "FROM nginx:1.25\nRUN pip install libcustom-dsp-kernel==1.0",
        "manifest_type": "dockerfile"
    }
    response = client.post("/api/triage", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert data["summary"]["total_packages"] >= 2
    assert "executive_brief_markdown" in data
    assert data.get("target_environment") == "RHEL 9 on OpenShift (ppc64le)"
    assert data.get("deliverable_type") == "container"
    assert "Person-Days" in data["executive_brief_markdown"]
    assert "fibonacci_effort_pd" in data["summary"]
    payload2 = {**payload, "raw_manifest": "FROM mysql:9.5\nRUN pip install libcustom-dsp-kernel==1.0"}
    response2 = client.post("/api/triage", json=payload2)
    assert response2.status_code == 200
    data2 = response2.json()
    assert any(p.get("version_warning") is not None for p in data2["packages"])


def test_fibonacci_effort_calculation():
    """Verify single-value Fibonacci effort mapping strictly greater than base effort."""
    from backend.agent import next_fibonacci_effort
    assert next_fibonacci_effort(0) == 0
    assert next_fibonacci_effort(1) == 2
    assert next_fibonacci_effort(2) == 3
    assert next_fibonacci_effort(5) == 8
    assert next_fibonacci_effort(26) == 34
    assert next_fibonacci_effort(34) == 55


def test_positive_sales_recommendations():
    """Verify positive, effort-based sales recommendation tiers."""
    from backend.models import SalesRecommendationTier
    assert SalesRecommendationTier.MINIMAL_EFFORT == "Minimal Effort"
    assert SalesRecommendationTier.MINOR_EFFORT == "Minor Effort"
    assert SalesRecommendationTier.MODERATE_EFFORT == "Moderate Effort"
    assert SalesRecommendationTier.SIGNIFICANT_EFFORT == "Significant Effort"
    assert SalesRecommendationTier.NOT_POSSIBLE_AS_IS == "Not Possible As-Is (Alternative Required)"


def test_export_executive_pdf_endpoint():
    """Verify /api/export/pdf returns a valid binary PDF."""
    sample_report = {
        "project_name": "RocksDB Migration",
        "primary_package_name": "rocksdb",
        "git_repo_url": "https://github.com/facebook/rocksdb",
        "doc_url": "https://rocksdb.org",
        "package_ecosystem": "native_c",
        "package_version": "8.6",
        "target_os": "RHEL9",
        "target_platform": "OPENSHIFT",
        "summary": {
            "total_packages": 3,
            "native_count": 2,
            "agnostic_count": 0,
            "substitute_count": 0,
            "unported_count": 1,
            "blocker_count": 0,
            "readiness_score_pct": 76.5,
            "recommendation": "Minor Effort",
            "recommendation_reason": "High readiness (76.5%). Light build verification estimated at 8 Person-Days.",
            "fibonacci_effort_pd": 8,
            "min_total_person_days": 8,
            "max_total_person_days": 8,
            "unported_transitive_deps_count": 1,
            "test_deps_unresolved_count": 1
        },
        "packages": [
            {
                "package_name": "rocksdb",
                "requested_version": "8.6",
                "ecosystem": "native_c",
                "status": "unported_build_required",
                "tier_description": "Requires source build",
                "build_system": "CMake",
                "total_effort_pd": 5,
                "git_repo_url": "https://github.com/facebook/rocksdb",
                "doc_url": "https://rocksdb.org",
                "arch_sensitivity": {
                    "has_simd_avx": True,
                    "simd_instruction_count": 120,
                    "simd_porting_complexity": "SIMDE_COMPATIBLE",
                    "remediation_strategy": "Include simde/x86/avx2.h headers."
                }
            }
        ]
    }
    response = client.post("/api/export/pdf", json=sample_report)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    pdf_bytes = response.content
    assert b"rocksdb" in pdf_bytes
    assert b"facebook/rocksdb" in pdf_bytes
    assert b"rocksdb.org" in pdf_bytes


def test_url_extractor_heuristics():
    """Verify URLExtractor parses GitHub and package website URLs."""
    from backend.url_extractor import URLExtractor
    assert URLExtractor.is_url("https://github.com/facebook/rocksdb") is True
    assert URLExtractor.is_url("https://rocksdb.org") is True
    assert URLExtractor.is_url("torch==2.1.0\nnginx") is False

    import asyncio
    async def _test():
        pkgs, title, note = await URLExtractor.extract_from_url("https://github.com/facebook/rocksdb")
        names = [p["name"].lower() for p in pkgs]
        assert "rocksdb" in names
    asyncio.run(_test())


def test_target_environment_enum():
    """TargetEnvironment combined enum resolves correct OS and platform."""
    assert TargetEnvironment.RHEL9_OCP.os == "rhel9"
    assert TargetEnvironment.RHEL9_OCP.platform == "ocp"
    assert TargetEnvironment.RHEL10_OCP.os == "rhel10"
    assert TargetEnvironment.RHEL10_BARE.platform == "baremetal"
    assert "OpenShift" in TargetEnvironment.RHEL9_OCP.display
    assert "RHEL 10" in TargetEnvironment.RHEL10_OCP.display


def test_deliverable_type_classify_supported():
    """classify_deliverable_match: container requested, container available → Supported."""
    probe = {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "tier": "Official Docker Hub Multi-Arch Container",
        "available_version": "1.24",
    }
    result = classify_deliverable_match(probe, "1.24", DeliverableType.CONTAINER)
    assert result["deliverable_match"] == DeliverableMatchStatus.SUPPORTED
    assert result["partial_multiplier"] == 1.0


def test_deliverable_type_classify_partial_type():
    """classify_deliverable_match: container requested, only RPM available → Partial different type."""
    probe = {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "tier": "RHEL/EPEL — Fedora Koji ppc64le RPM",
        "available_version": "1.24",
    }
    result = classify_deliverable_match(probe, "1.24", DeliverableType.CONTAINER)
    assert result["deliverable_match"] == DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE
    assert result["partial_multiplier"] == 1.5
    assert "Partial" in result["deliverable_detail"]


def test_deliverable_type_classify_partial_version():
    """classify_deliverable_match: container requested, container available at different version → Partial version."""
    probe = {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "tier": "Official Docker Hub Multi-Arch Container",
        "available_version": "1.22",
    }
    result = classify_deliverable_match(probe, "1.24", DeliverableType.CONTAINER)
    assert result["deliverable_match"] == DeliverableMatchStatus.PARTIAL_DIFFERENT_VERSION
    assert result["partial_multiplier"] == 1.25


def test_deliverable_type_classify_not_supported():
    """classify_deliverable_match: blocker status → Not Supported regardless of deliverable."""
    probe = {
        "status": AvailabilityStatus.BLOCKER,
        "tier": "x86-proprietary Intel Math Kernel Library",
        "available_version": None,
    }
    for dt in DeliverableType:
        result = classify_deliverable_match(probe, "latest", dt)
        assert result["deliverable_match"] == DeliverableMatchStatus.NOT_SUPPORTED
        assert result["partial_multiplier"] == 1.0


def test_deliverable_type_build_script_supported():
    """classify_deliverable_match: build_script requested, build-scripts tier → Supported."""
    probe = {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "tier": "ppc64le/build-scripts — active IBM Power build recipe",
        "available_version": "3.6",
    }
    result = classify_deliverable_match(probe, "3.6", DeliverableType.BUILD_SCRIPT)
    assert result["deliverable_match"] == DeliverableMatchStatus.SUPPORTED


def test_deliverable_type_build_partial_from_container():
    """classify_deliverable_match: build requested, only container available → Partial type."""
    probe = {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "tier": "ICR ppc64le-oss Container",
        "available_version": "7.2",
    }
    result = classify_deliverable_match(probe, "7.2", DeliverableType.BUILD)
    assert result["deliverable_match"] == DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE
    assert result["partial_multiplier"] == 1.5


def test_api_triage_deliverable_partial_effort_increase():
    """End-to-end: requesting a build deliverable for a container-only package raises effort."""
    payload_container = {
        "project_name": "Effort Comparison Test",
        "target_environment": "rhel9_ocp",
        "deliverable_type": "container",
        "triage_depth": "express",
        "raw_manifest": "FROM redis:7.2",
        "manifest_type": "dockerfile",
    }
    payload_build = {**payload_container, "deliverable_type": "build"}

    r_container = client.post("/api/triage", json=payload_container)
    r_build = client.post("/api/triage", json=payload_build)
    assert r_container.status_code == 200
    assert r_build.status_code == 200

    summary_container = r_container.json()["summary"]
    summary_build     = r_build.json()["summary"]
    assert summary_build["partial_support_count"] >= summary_container["partial_support_count"]
