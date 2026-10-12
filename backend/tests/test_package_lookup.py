"""
Unit tests for PackageLookupManager and persistent dynamic package lookup file.
"""

import json
import pytest
import tempfile
from pathlib import Path

from backend.package_lookup import PackageLookupManager, normalize_status
from backend.models import AvailabilityStatus, DeliverableType
from backend.prober import MultiSourceProber


def test_normalize_status():
    assert normalize_status("NATIVE_AVAILABLE") == AvailabilityStatus.NATIVE_AVAILABLE
    assert normalize_status("native_available") == AvailabilityStatus.NATIVE_AVAILABLE
    assert normalize_status(AvailabilityStatus.BLOCKER) == AvailabilityStatus.BLOCKER
    assert normalize_status("unknown_status") == AvailabilityStatus.UNPORTED_BUILD_REQUIRED


def test_lookup_manager_load_and_get():
    """Verify loading from JSON file and retrieving known package."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "packages_lookup.json"
        initial_data = {
            "testpkg": {
                "package_name": "testpkg",
                "version": "1.0.0",
                "status": "native_available",
                "available_version": "1.0.0",
                "tier": "Official container",
                "evidence": "Verified",
                "url": "https://example.com/testpkg",
                "versions": {
                    "1.0.0": {
                        "status": "native_available",
                        "available_version": "1.0.0",
                    }
                }
            }
        }
        json_path.write_text(json.dumps(initial_data), encoding="utf-8")

        mgr = PackageLookupManager(filepath=json_path)

        # Exact version hit
        res_v1 = mgr.get("testpkg", "1.0.0")
        assert res_v1 is not None
        assert res_v1["cached_hit"] is True
        assert res_v1["status"] == AvailabilityStatus.NATIVE_AVAILABLE

        # Latest version hit
        res_latest = mgr.get("testpkg", "latest")
        assert res_latest is not None
        assert res_latest["cached_hit"] is True

        # Case insensitive hit
        res_case = mgr.get("TESTPKG", "1.0.0")
        assert res_case is not None

        # Unknown package returns None
        assert mgr.get("nonexistent_pkg") is None


def test_lookup_manager_new_version_cache_miss():
    """When a new/different version analysis is requested, return None to trigger fresh analysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "packages_lookup.json"
        initial_data = {
            "myredis": {
                "package_name": "myredis",
                "version": "7.0",
                "status": "native_available",
                "available_version": "7.0",
            }
        }
        json_path.write_text(json.dumps(initial_data), encoding="utf-8")
        mgr = PackageLookupManager(filepath=json_path)

        # Version 7.0 is cached
        assert mgr.get("myredis", "7.0") is not None

        # Version 7.2 is a NEW version analysis request -> must return None so LLM/probe evaluates it
        assert mgr.get("myredis", "7.2") is None


def test_lookup_manager_save_and_refresh():
    """Verify save_or_refresh updates in-memory cache and persists back to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "packages_lookup.json"
        mgr = PackageLookupManager(filepath=json_path)

        # Initial save of package
        mgr.save_or_refresh(
            package_name="custom-ai-lib",
            version="2.0",
            probe_result={
                "status": "native_available",
                "available_version": "2.0",
                "tier": "Native ppc64le build",
                "evidence": "Live analysis",
                "url": "https://example.com/custom-ai-lib",
            },
            metadata={
                "git_repo_url": "https://github.com/example/custom-ai-lib",
                "doc_url": "https://example.com/docs",
                "ecosystem": "native_c",
            }
        )

        # Check it can be retrieved
        cached = mgr.get("custom-ai-lib", "2.0")
        assert cached is not None
        assert cached["version"] == "2.0"
        assert cached["status"] == AvailabilityStatus.NATIVE_AVAILABLE

        # Check JSON file on disk was written
        assert json_path.exists()
        disk_data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "custom-ai-lib" in disk_data
        assert disk_data["custom-ai-lib"]["versions"]["2.0"]["status"] == "native_available"

        # Now simulate a new version request and refresh: 2.1
        mgr.save_or_refresh(
            package_name="custom-ai-lib",
            version="2.1",
            probe_result={
                "status": "native_available",
                "available_version": "2.1",
                "tier": "Native ppc64le build v2.1",
            }
        )

        refreshed = mgr.get("custom-ai-lib", "2.1")
        assert refreshed is not None
        assert refreshed["version"] == "2.1"
        assert "2.0" in refreshed["versions"]
        assert "2.1" in refreshed["versions"]


@pytest.mark.asyncio
async def test_prober_reuses_lookup_without_llm():
    """Verify MultiSourceProber reuses lookup file and does not make external calls."""
    prober = MultiSourceProber()
    # nginx is in the lookup file at version 1.24
    res = await prober.probe_component("nginx", "1.24", "container", "rhel9", DeliverableType.CONTAINER)
    assert res is not None
    assert res.get("status") == AvailabilityStatus.NATIVE_AVAILABLE
    assert res.get("deliverable_match") is not None


def test_lookup_manager_env_path_resolution(monkeypatch):
    """Verify PACKAGE_LOOKUP_PATH environment variable overrides default path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        custom_file = Path(tmpdir) / "custom_lookup.json"
        custom_file.write_text(json.dumps({"envpkg": {"package_name": "envpkg", "status": "native_available"}}))
        monkeypatch.setenv("PACKAGE_LOOKUP_PATH", str(custom_file))

        mgr = PackageLookupManager()
        assert str(mgr.filepath) == str(custom_file)
        assert mgr.get("envpkg") is not None


def test_lookup_manager_mtime_auto_reload():
    """Verify PackageLookupManager reloads when mounted file on disk is modified externally."""
    import time
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "packages_lookup.json"
        json_path.write_text(json.dumps({"pkg_a": {"package_name": "pkg_a", "status": "native_available"}}), encoding="utf-8")

        mgr = PackageLookupManager(filepath=json_path)
        assert mgr.get("pkg_a") is not None
        assert mgr.get("pkg_b") is None

        # Simulate host/external edit to mounted file
        time.sleep(0.05)
        json_path.write_text(
            json.dumps({
                "pkg_a": {"package_name": "pkg_a", "status": "native_available"},
                "pkg_b": {"package_name": "pkg_b", "status": "native_available", "version": "1.0"},
            }),
            encoding="utf-8"
        )

        # mgr should detect mtime update and reload pkg_b automatically
        res_b = mgr.get("pkg_b")
        assert res_b is not None
        assert res_b["version"] == "1.0"


def test_lookup_manager_get_info():
    """Verify get_info returns mounting status, path, and package count."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "packages_lookup.json"
        json_path.write_text(json.dumps({"pkg1": {"package_name": "pkg1"}}), encoding="utf-8")
        mgr = PackageLookupManager(filepath=json_path)
        info = mgr.get_info()
        assert info["is_mounted"] is True
        assert info["package_count"] == 1
        assert "pkg1" in info["packages"]
        assert info["last_modified"] is not None

