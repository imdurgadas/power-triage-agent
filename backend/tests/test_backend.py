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
    TriageRequest,
    SIMDPortingComplexity,
    TestDependency as PpcTestDependency,
)

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

        res_sub = await prober.probe_component("torch", "2.1.0", "pypi", "rhel9")
        assert res_sub["status"] == AvailabilityStatus.SUBSTITUTE_AVAILABLE

        # Test zlib is recognized as core native library (0 PD)
        res_zlib = await prober.probe_component("zlib", "1.2.11", "native_c", "rhel9")
        assert res_zlib["status"] == AvailabilityStatus.NATIVE_AVAILABLE
        assert "BaseOS" in res_zlib["evidence"]

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
        # Case: Requested version exceeds available cache version (nginx available is 1.24, requested 1.25)
        res_newer = await prober.probe_component("nginx", "1.25", "container", "rhel9")
        assert res_newer["status"] == AvailabilityStatus.UNPORTED_BUILD_REQUIRED
        assert "version_warning" in res_newer
        assert "exceeds verified ppc64le version" in res_newer["version_warning"]

        # Case: Requested version is older than available version (nginx requested 1.20 vs available 1.24)
        res_older = await prober.probe_component("nginx", "1.20", "container", "rhel9")
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
        "target_os": "rhel9",
        "target_platform": "ocp",
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
    # Verify version warning was captured for nginx:1.25
    assert any(p.get("version_warning") is not None for p in data["packages"])
    # Verify Total Person Days is present
    assert "Total Person Days" in data["executive_brief_markdown"]
