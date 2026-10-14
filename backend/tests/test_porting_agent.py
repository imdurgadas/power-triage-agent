"""
test_porting_agent.py
Tests for the Autonomous Power Porting Agent, environment manager,
plan generator, and API endpoints.
"""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import (
    PowerVMConfig,
    PortingJobRequest,
    PortingActionType,
)
from backend.power_env import MockPowerEnvironment, get_power_environment
from backend.porting_planner import formulate_porting_plan
from backend.porting_agent import AutonomousPortingOrchestrator, PORTING_JOBS


@pytest.mark.asyncio
async def test_mock_power_environment_diagnostics():
    config = PowerVMConfig(host="mock", use_mock=True)
    env = get_power_environment(config)
    assert isinstance(env, MockPowerEnvironment)

    info = await env.connect()
    assert info["architecture"] == "ppc64le"
    assert "65536" in info["page_size"]
    assert info["vsx_support"] is True
    assert "POWER10" in info["cpu_model"]


@pytest.mark.asyncio
async def test_mock_power_environment_build_and_patch_cycle():
    config = PowerVMConfig(host="mock", use_mock=True)
    env = MockPowerEnvironment(config)
    await env.connect()

    # Baseline build fails initially due to SIMD immintrin.h missing on ppc64le
    code, stdout, stderr = await env.execute("python -m build --wheel")
    assert code != 0
    assert "immintrin.h" in stderr or "No such file" in stderr

    # Apply Power-specific patch
    patch_code = """
    #if defined(__powerpc__) || defined(__PPC64__)
    #include <altivec.h>
    #endif
    """
    await env.write_file("/tmp/power_porting/simd.h", patch_code)

    # Subsequent build succeeds with ppc64le VSX
    code, stdout, stderr = await env.execute("python -m build --wheel")
    assert code == 0
    assert "VSX" in stdout or "linux_ppc64le.whl" in stdout

    # Test run succeeds
    code, stdout, stderr = await env.execute("pytest -v tests/")
    assert code == 0
    assert "18 passed" in stdout


def test_porting_planner_wheel_and_simd():
    triage_finding = {
        "git_repo_url": "https://github.com/custom/dsp-engine",
        "arch_sensitivity": {
            "has_simd_avx": True,
            "has_64k_page_risk": True,
        }
    }
    plan = formulate_porting_plan(
        package_name="custom-dsp-engine",
        version="1.2.0",
        ecosystem="python",
        deliverable_target="wheel",
        triage_finding=triage_finding,
    )
    assert plan.action_type == PortingActionType.BUILD_WHEEL
    assert any("SIMD" in s or "AVX" in s for s in plan.detected_sensitivities)
    assert any("64KB" in s for s in plan.detected_sensitivities)
    assert "simde-devel" in plan.prerequisites
    assert any("build --wheel" in cmd for cmd in plan.build_commands)


def test_porting_planner_container():
    plan = formulate_porting_plan(
        package_name="rocksdb-service",
        version="8.6.0",
        ecosystem="container",
        deliverable_target="container",
    )
    assert plan.action_type == PortingActionType.CREATE_CONTAINER
    assert "podman" in plan.prerequisites
    assert any("podman build --arch ppc64le" in cmd for cmd in plan.build_commands)


@pytest.mark.asyncio
async def test_autonomous_orchestrator_end_to_end():
    req = PortingJobRequest(
        package_name="libcustom-dsp-engine",
        version="1.2.0",
        ecosystem="python",
        deliverable_target="wheel",
        git_repo_url="https://github.com/example/dsp-engine",
        upstream_repo="example/dsp-engine",
        vm_config=PowerVMConfig(use_mock=True, host="mock"),
    )

    orchestrator = AutonomousPortingOrchestrator(req)
    result = await orchestrator.execute()

    assert result.status == "completed"
    assert len(result.steps) == 7
    assert result.steps[1].title == "Target OS Container Creation & Workspace Setup"
    for step in result.steps:
        assert step.status == "completed"

    # Container environment verified
    assert "os_name" in result.container_info
    assert "container_id" in result.container_info

    # Architecture patch generated with non-breaking guards
    assert result.diff is not None
    assert "__powerpc__" in result.diff
    assert "__x86_64__" in result.diff

    # Tests executed and verified
    assert result.test_summary["passed"] >= 18
    assert result.test_summary["pass_rate_pct"] == 100.0

    # Evidence report contains hardware and testing proof
    assert result.evidence_report_markdown is not None
    assert "ppc64le" in result.evidence_report_markdown
    # When no GitHub token is provided, changes are committed to git branch without fake PR simulation
    assert result.pr_url is None


def test_api_porting_endpoints():
    client = TestClient(app)

    # 1. Test VM connection
    vm_payload = {"host": "mock", "port": 22, "username": "root", "use_mock": True}
    res = client.post("/api/porting/test-connection", json=vm_payload)
    assert res.status_code == 200
    assert res.json()["system_info"]["architecture"] == "ppc64le"

    # 2. Formulate plan
    job_req = {
        "package_name": "simdjson",
        "version": "3.6.0",
        "deliverable_target": "source",
        "vm_config": vm_payload,
    }
    res = client.post("/api/porting/plan", json=job_req)
    assert res.status_code == 200
    plan_data = res.json()
    assert plan_data["package_name"] == "simdjson"
    assert plan_data["action_type"] == "build_from_source"

    # 3. Start porting job
    res = client.post("/api/porting/start", json=job_req)
    assert res.status_code == 200
    job_data = res.json()
    job_id = job_data["job_id"]
    assert job_id in PORTING_JOBS

    # 4. Query status
    res = client.get(f"/api/porting/status/{job_id}")
    assert res.status_code == 200
    assert res.json()["job_id"] == job_id
