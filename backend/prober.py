import asyncio
import re
import json
import xmlrpc.client
import httpx
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache, partial
from pathlib import Path
from typing import Dict, Any, Optional, List
from .models import AvailabilityStatus, DeliverableType, DeliverableMatchStatus, _PARTIAL_EFFORT_MULTIPLIERS
from .gemini_helper import generate_gemini_content

# Thread-pool for running blocking XMLRPC calls off the async event loop
_SYNC_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="prober_sync")


async def _run_sync(fn, *args):
    """Run a blocking callable in the shared thread-pool and await the result."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_SYNC_EXECUTOR, partial(fn, *args))

logger = logging.getLogger("prober")

# ---------------------------------------------------------------------------
# Local index data — loaded once at import time from pre-built JSON files.
# Re-generated monthly by:  python3 backend/data/refresh_indexes.py
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=1)
def _load_devpi_index() -> Dict[str, Any]:
    """Return the ppc64le/pyeco DevPi wheels index (package_name → metadata)."""
    path = _DATA_DIR / "devpi_wheels_index.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("packages", {})
        except Exception as exc:
            logger.warning("Could not load devpi_wheels_index.json: %s", exc)
    return {}


@lru_cache(maxsize=1)
def _load_icr_index() -> Dict[str, List[Dict]]:
    """Return the ICR Power Image Tracker lookup (canonical_name → list of entries)."""
    path = _DATA_DIR / "icr_power_images.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("lookup", {})
        except Exception as exc:
            logger.warning("Could not load icr_power_images.json: %s", exc)
    return {}


@lru_cache(maxsize=1)
def _load_build_scripts_index() -> Dict[str, Any]:
    """Return the ppc64le/build-scripts lookup (package_name → build_info entry)."""
    path = _DATA_DIR / "build_scripts_index.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("lookup", {})
        except Exception as exc:
            logger.warning("Could not load build_scripts_index.json: %s", exc)
    return {}


def compare_versions(requested: str, available: str) -> int:
    """Compares requested version against available version.
    Returns:
       1 if requested > available (requested is newer)
      -1 if requested < available (requested is older)
       0 if equal or cannot determine or requested is 'latest'
    """
    if not requested or not available:
        return 0
    req_s = str(requested).strip().lstrip("v").lower()
    avail_s = str(available).strip().lstrip("v").lower()
    if req_s in ["latest", "master", "main", ""]:
        return 0
    if req_s == avail_s:
        return 0
    try:
        from packaging import version as pkg_v
        v1 = pkg_v.parse(req_s)
        v2 = pkg_v.parse(avail_s)
        if v1 > v2:
            return 1
        elif v1 < v2:
            return -1
        return 0
    except Exception:
        def _parse(s):
            chunks = re.split(r"[\.-]", s)
            res = []
            for c in chunks:
                if c.isdigit():
                    res.append(int(c))
                else:
                    res.append(c)
            return tuple(res)
        try:
            t1 = _parse(req_s)
            t2 = _parse(avail_s)
            if t1 > t2:
                return 1
            elif t1 < t2:
                return -1
            return 0
        except Exception:
            return 0


# Pre-compiled high-fidelity database of known Power ecosystem components to provide instant responses
# and augment live API checks
POWER_ECOSYSTEM_CACHE = {
    # Containers with native ppc64le multi-arch tags on Docker Hub / Quay / Red Hat Registry
    "nginx": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "1.24", "tier": "Official multi-arch container", "evidence": "Docker Hub Official (linux/ppc64le)", "url": "https://hub.docker.com/_/nginx"},
    "redis": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "7.2", "tier": "Official multi-arch container", "evidence": "Docker Hub Official (linux/ppc64le)", "url": "https://hub.docker.com/_/redis"},
    "postgres": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "15.0", "tier": "Official multi-arch container", "evidence": "Docker Hub Official (linux/ppc64le)", "url": "https://hub.docker.com/_/postgres"},
    "postgresql": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "15.0", "tier": "Official multi-arch container", "evidence": "Docker Hub Official (linux/ppc64le)", "url": "https://hub.docker.com/_/postgres"},
    "mysql": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "8.0", "tier": "Red Hat / CentOS Stream container", "evidence": "Red Hat Ecosystem Catalog (ppc64le)", "url": "https://catalog.redhat.com"},
    "kafka": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "3.6.0", "tier": "Red Hat Strimzi / Apache Kafka multi-arch", "evidence": "Quay.io/strimzi/kafka (linux on ppc64le verified)", "url": "https://quay.io/repository/strimzi/kafka"},
    "strimzi/kafka": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "3.6.0", "tier": "Red Hat Strimzi / Apache Kafka multi-arch", "evidence": "Quay.io/strimzi/kafka (linux on ppc64le verified)", "url": "https://quay.io/repository/strimzi/kafka"},
    "rabbitmq": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "3.12", "tier": "Official multi-arch container", "evidence": "Docker Hub Official (linux/ppc64le)", "url": "https://hub.docker.com/_/rabbitmq"},
    "node": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "20.0", "tier": "Official multi-arch container", "evidence": "Docker Hub Official (linux/ppc64le)", "url": "https://hub.docker.com/_/node"},
    "python": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "3.11", "tier": "Official multi-arch container", "evidence": "Docker Hub Official (linux/ppc64le)", "url": "https://hub.docker.com/_/python"},
    "golang": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "available_version": "1.21", "tier": "Official multi-arch container", "evidence": "Docker Hub Official (linux/ppc64le)", "url": "https://hub.docker.com/_/golang"},

    # Core System & Compression Libraries natively shipped in all Linux distributions for ppc64le
    "zlib": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "available_version": "1.2.11",
        "tier": "Core OS Library / Compression",
        "evidence": "Native package in RHEL / SLES / Ubuntu BaseOS (zlib, zlib-devel ppc64le with hardware vector acceleration)",
        "url": "https://www.zlib.net"
    },
    "zlib-devel": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "available_version": "1.2.11",
        "tier": "Core OS Development Headers",
        "evidence": "RHEL / SLES / Ubuntu BaseOS ppc64le",
        "url": "https://www.zlib.net"
    },
    "libz": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "available_version": "1.2.11",
        "tier": "Core OS Library / Compression",
        "evidence": "Standard shared library in Linux on Power (ppc64le)",
        "url": "https://www.zlib.net"
    },
    "libdeflate": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "available_version": "1.18",
        "tier": "EPEL 9 repository for ppc64le",
        "evidence": "EPEL 9 ppc64le / Conda-forge",
        "url": "https://packages.fedoraproject.org/pkgs/libdeflate/"
    },
    "openssl": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "available_version": "3.0.7",
        "tier": "Core OS Library / Cryptography",
        "evidence": "Native package in RHEL / SLES / Ubuntu BaseOS ppc64le",
        "url": "https://www.openssl.org"
    },
    "openssl-devel": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "available_version": "3.0.7",
        "tier": "Core OS Development Headers",
        "evidence": "RHEL / SLES / Ubuntu BaseOS ppc64le",
        "url": "https://www.openssl.org"
    },
    "snappy": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "available_version": "1.2.2",
        "tier": "Core OS Library",
        "evidence": "RHEL 8/9 AppStream ppc64le; ppc64le/build-scripts v1.2.2",
        "url": "https://github.com/google/snappy"
    },
    "lz4": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "tier": "Core OS Library",
        "evidence": "RHEL 8/9 AppStream ppc64le",
        "url": "https://github.com/lz4/lz4"
    },

    # Python packages with native ppc64le wheels or Open-CE support
    "numpy": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "tier": "PyPI native ppc64le wheel", "evidence": "PyPI release (ppc64le wheel available)", "url": "https://pypi.org/project/numpy"},
    "pandas": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "tier": "PyPI native ppc64le wheel", "evidence": "PyPI release (ppc64le wheel available)", "url": "https://pypi.org/project/pandas"},
    "scipy": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "tier": "PyPI native ppc64le wheel", "evidence": "PyPI release (ppc64le wheel available)", "url": "https://pypi.org/project/scipy"},
    # torch and tensorflow are intentionally absent here — the ppc64le/pyeco DevPi
    # wheels index has native ppc64le wheels for both and is more authoritative.
    # _probe_devpi_wheels() handles them and returns NATIVE_AVAILABLE.
    # pytorch (conda name, no devpi entry) and faiss (no devpi entry) remain below.
    "pytorch": {
        "status": AvailabilityStatus.SUBSTITUTE_AVAILABLE,
        "tier": "IBM Open-CE optimized package",
        "evidence": "IBM Open-CE / RocketCE repository (conda-forge ppc64le)",
        "url": "https://github.com/open-ce/open-ce",
        "substitute": "open-ce/pytorch-ppc64le (optimized with Power VSX / MMA)"
    },
    "fastapi": {"status": AvailabilityStatus.PLATFORM_AGNOSTIC, "tier": "Pure Python package (noarch)", "evidence": "PyPI (py2.py3-none-any.whl)", "url": "https://pypi.org/project/fastapi"},
    "flask": {"status": AvailabilityStatus.PLATFORM_AGNOSTIC, "tier": "Pure Python package (noarch)", "evidence": "PyPI (py2.py3-none-any.whl)", "url": "https://pypi.org/project/flask"},
    "requests": {"status": AvailabilityStatus.PLATFORM_AGNOSTIC, "tier": "Pure Python package (noarch)", "evidence": "PyPI (py2.py3-none-any.whl)", "url": "https://pypi.org/project/requests"},
    "pydantic": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "tier": "PyPI native ppc64le wheel", "evidence": "PyPI release (pydantic-core ppc64le wheel)", "url": "https://pypi.org/project/pydantic"},

    # NOTE: rocksdb and simdjson have active build recipes in ppc64le/build-scripts
    # and are intentionally absent here so _probe_build_scripts() handles them.
    "faiss": {
        "status": AvailabilityStatus.SUBSTITUTE_AVAILABLE,
        "tier": "IBM Open-CE optimized build",
        "evidence": "Conda-forge / Open-CE channel",
        "url": "https://github.com/open-ce/open-ce",
        "substitute": "open-ce/faiss-ppc64le"
    },

    # Math Kernel Libraries
    "intel-mkl": {
        "status": AvailabilityStatus.BLOCKER,
        "tier": "x86-proprietary Intel Math Kernel Library",
        "evidence": "Intel closed-source binary library; only supports x86_64 architecture",
        "url": "https://www.intel.com/content/www/us/en/developer/tools/oneapi/onemkl.html",
        "substitute": "IBM ESSL (Engineering and Scientific Subroutine Library) or OpenBLAS / BLIS (MMA/VSX accelerated)"
    },
    "mkl": {
        "status": AvailabilityStatus.BLOCKER,
        "tier": "x86-proprietary Intel Math Kernel Library",
        "evidence": "Intel closed-source binary library; only supports x86_64 architecture",
        "url": "https://www.intel.com/content/www/us/en/developer/tools/oneapi/onemkl.html",
        "substitute": "IBM ESSL (Engineering and Scientific Subroutine Library) or OpenBLAS / BLIS (MMA/VSX accelerated)"
    },
    "openblas": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "tier": "Native High-Performance BLAS / Math Library",
        "evidence": "RHEL AppStream / EPEL ppc64le (optimized with Power10 MMA / Power9 VSX)",
        "url": "https://www.openblas.net"
    },
    "blis": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "tier": "Native BLAS Library Framework",
        "evidence": "Fedora / EPEL / Source (Power VSX accelerated)",
        "url": "https://github.com/flame/blis"
    },
    "essl": {
        "status": AvailabilityStatus.NATIVE_AVAILABLE,
        "tier": "IBM Engineering and Scientific Subroutine Library",
        "evidence": "IBM Power native high-performance mathematical computing library",
        "url": "https://www.ibm.com/products/engineering-scientific-subroutine-library"
    }
}


def classify_deliverable_match(
    probe_result: Dict[str, Any],
    requested_version: str,
    deliverable_type: DeliverableType,
) -> Dict[str, Any]:
    """
    Overlays a deliverable-type aware support label on an existing probe result.

    Rules
    -----
    • container deliverable:
        - available_type == container  AND version matches  → Supported
        - available_type == container  AND version differs  → Partial, different version
        - available_type != container  (e.g. RPM / wheel)   → Partial, different artifact type
        - status is BLOCKER / UNPORTED                      → Not Supported
    • build deliverable:
        - available_type has an RPM / wheel / source build  → Supported
        - only a container is available                     → Partial, different artifact type
        - status is BLOCKER                                 → Not Supported
    • build_script deliverable:
        - build-scripts index or build recipe available     → Supported
        - something else is available                       → Partial, different artifact type
        - nothing available                                 → Not Supported

    Returns a copy of probe_result with two extra keys added:
        deliverable_match  : DeliverableMatchStatus
        deliverable_detail : str
        partial_multiplier : float  (effort multiplier to apply)
    """
    result = probe_result.copy()
    status: AvailabilityStatus = result.get("status", AvailabilityStatus.UNPORTED_BUILD_REQUIRED)
    tier: str = (result.get("tier") or "").lower()
    avail_ver: str = (result.get("available_version") or "").strip().lstrip("v")
    req_ver: str = (requested_version or "latest").strip().lstrip("v")

    # Not supported — blockers and explicit unported are always NOT_SUPPORTED regardless of deliverable
    if status in (AvailabilityStatus.BLOCKER, AvailabilityStatus.UNPORTED_BUILD_REQUIRED):
        result["deliverable_match"] = DeliverableMatchStatus.NOT_SUPPORTED
        result["deliverable_detail"] = (
            "Not Supported — no pre-built ppc64le artefact available; source porting required."
            if status == AvailabilityStatus.UNPORTED_BUILD_REQUIRED
            else "Not Supported — proprietary x86 blocker with no Power equivalent."
        )
        result["partial_multiplier"] = 1.0
        return result

    # Helper: does the tier string indicate a container artefact?
    def _is_container(t: str) -> bool:
        return any(k in t for k in ("container", "docker", "quay", "icr", "multi-arch", "image"))

    # Helper: does the tier string indicate a source build / RPM / wheel artefact?
    def _is_build(t: str) -> bool:
        return any(k in t for k in ("rpm", "wheel", "build-scripts", "devpi", "koji", "source", "pypi", "npm", "maven", "native"))

    # Helper: does the tier indicate a build script recipe exists?
    def _is_build_script(t: str) -> bool:
        return "build-scripts" in t or "recipe" in t or "build script" in t

    # Version match helper (only meaningful when a specific version was requested)
    def _version_mismatch() -> bool:
        if req_ver in ("latest", "master", "main", "") or not avail_ver:
            return False
        try:
            from packaging import version as pkg_v
            return pkg_v.parse(req_ver) != pkg_v.parse(avail_ver)
        except Exception:
            return req_ver != avail_ver

    is_container = _is_container(tier)
    is_build     = _is_build(tier)
    is_script    = _is_build_script(tier)
    ver_mismatch = _version_mismatch()

    match = DeliverableMatchStatus.SUPPORTED
    detail = ""
    multiplier = 1.0

    if deliverable_type == DeliverableType.CONTAINER:
        if is_container:
            if ver_mismatch:
                match  = DeliverableMatchStatus.PARTIAL_DIFFERENT_VERSION
                detail = f"Partial Support — container available but at version {avail_ver} (requested {req_ver})."
            else:
                match  = DeliverableMatchStatus.SUPPORTED
                detail = f"Supported — ppc64le container image available (version {avail_ver or 'latest'})."
        elif is_build or is_script or status == AvailabilityStatus.PLATFORM_AGNOSTIC:
            match  = DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE
            detail = f"Partial Support — no container image available; an RPM/wheel/build artefact exists. Containerisation effort required."
        else:
            match  = DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE
            detail = "Partial Support — indirect availability; manual containerisation for ppc64le required."

    elif deliverable_type == DeliverableType.BUILD:
        if is_build or is_script or status == AvailabilityStatus.PLATFORM_AGNOSTIC:
            if ver_mismatch:
                match  = DeliverableMatchStatus.PARTIAL_DIFFERENT_VERSION
                detail = f"Partial Support — build artefact available at version {avail_ver} (requested {req_ver})."
            else:
                match  = DeliverableMatchStatus.SUPPORTED
                detail = "Supported — pre-built ppc64le RPM/wheel/source build available."
        elif is_container:
            match  = DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE
            detail = "Partial Support — only a container image is available; extraction or source build from container needed."
        else:
            match  = DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE
            detail = "Partial Support — substitute available but artefact type differs from requested build."

    elif deliverable_type == DeliverableType.BUILD_SCRIPT:
        if is_script:
            if ver_mismatch:
                match  = DeliverableMatchStatus.PARTIAL_DIFFERENT_VERSION
                detail = f"Partial Support — build script exists at version {avail_ver} (requested {req_ver}); script update required."
            else:
                match  = DeliverableMatchStatus.SUPPORTED
                detail = "Supported — IBM ppc64le/build-scripts recipe exists for this package."
        elif is_build or is_container or status == AvailabilityStatus.PLATFORM_AGNOSTIC:
            match  = DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE
            detail = "Partial Support — pre-built artefact or container exists, but no dedicated build script. Script authoring required."
        else:
            match  = DeliverableMatchStatus.PARTIAL_DIFFERENT_TYPE
            detail = "Partial Support — substitute or indirect availability; build script authoring required."

    multiplier = _PARTIAL_EFFORT_MULTIPLIERS[match]
    result["deliverable_match"] = match
    result["deliverable_detail"] = detail
    result["partial_multiplier"] = multiplier
    return result


class MultiSourceProber:
    """Probes Docker Hub, Quay.io, PyPI, RHEL/EPEL Koji, ICR Power catalogue,
    ppc64le/pyeco DevPi wheels index, ppc64le/build-scripts, and Gemini LLM."""

    def __init__(self, gemini_client=None):
        self._cache = POWER_ECOSYSTEM_CACHE.copy()
        self.gemini_client = gemini_client

    def set_gemini_client(self, client):
        self.gemini_client = client

    async def probe_component(
        self,
        name: str,
        version: str = "latest",
        ecosystem: str = "container",
        target_os: str = "rhel9",
        deliverable_type: DeliverableType = DeliverableType.CONTAINER,
    ) -> Dict[str, Any]:
        norm_name = name.lower().strip()

        # Clean image prefixes if container
        clean_name = norm_name
        if clean_name.startswith("quay.io/"):
            clean_name = clean_name.replace("quay.io/", "")
            ecosystem = "quay"
        elif clean_name.startswith("docker.io/"):
            clean_name = clean_name.replace("docker.io/", "")

        # Probe priority order:
        #   RedHat distro repos and Docker Hub take precedence over IBM-specific
        #   sources (build-scripts, ICR) so that the most broadly available and
        #   maintained package is always preferred.
        #
        #   1. RHEL/EPEL Koji          — Red Hat distro repositories (rpm/native/container)
        #   2. Docker Hub / Quay live  — container registries
        #   3. PyPI live               — Python packages
        #   4. DevPi wheels index      — IBM pyeco (Python only, fallback)
        #   5. ICR Power catalogue     — IBM Container Registry (container fallback)
        #   6. build-scripts index     — IBM build recipes (last resort before static cache)
        #   7. Static cache            — hand-curated entries (e.g. mkl blocker, essl, blis)
        #   8. Gemini LLM              — AI research for unknown packages
        #   9. Default fallback

        # 1. RHEL/EPEL Koji repository check (rpm ecosystem, native C/C++, containers, or any RHEL target)
        if ecosystem in ["rpm", "native_c", "container"] or target_os.startswith("rhel"):
            rhel_res = await self._probe_rhel_epel(clean_name, version)
            if rhel_res:
                self._cache[clean_name] = rhel_res
                return classify_deliverable_match(rhel_res, version, deliverable_type)

        # 2. Live API check for container registries (Docker Hub / Quay)
        if ecosystem in ["container", "docker", "quay"] or "/" in clean_name:
            if ecosystem == "quay" or "strimzi" in clean_name or "redhat" in clean_name:
                quay_res = await self._probe_quay(clean_name, version)
                if quay_res and quay_res.get("status") == AvailabilityStatus.NATIVE_AVAILABLE:
                    self._cache[clean_name] = quay_res
                    return classify_deliverable_match(quay_res, version, deliverable_type)

            docker_res = await self._probe_docker_hub(clean_name, version)
            if docker_res and docker_res.get("status") == AvailabilityStatus.NATIVE_AVAILABLE:
                self._cache[clean_name] = docker_res
                return classify_deliverable_match(docker_res, version, deliverable_type)

        # 3. Live API check for PyPI
        if ecosystem == "pypi":
            pypi_res = await self._probe_pypi(clean_name, version)
            if pypi_res and pypi_res.get("status") in [AvailabilityStatus.NATIVE_AVAILABLE, AvailabilityStatus.PLATFORM_AGNOSTIC]:
                self._cache[clean_name] = pypi_res
                return classify_deliverable_match(pypi_res, version, deliverable_type)

        # 4. ppc64le/pyeco DevPi wheels index (Python only — IBM fallback)
        if ecosystem == "pypi":
            devpi_res = self._probe_devpi_wheels(clean_name, version)
            if devpi_res:
                self._cache[clean_name] = devpi_res
                return classify_deliverable_match(devpi_res, version, deliverable_type)

        # 5. ICR Power catalogue (containers only — IBM fallback)
        if ecosystem in ["container", "docker", "quay"] or "/" in clean_name:
            icr_res = self._probe_icr_power(clean_name, version)
            if icr_res:
                self._cache[clean_name] = icr_res
                return classify_deliverable_match(icr_res, version, deliverable_type)

        # 6. ppc64le/build-scripts index — IBM build recipes (any ecosystem, last resort before cache)
        bs_res = self._probe_build_scripts(clean_name, version)
        if bs_res:
            self._cache[clean_name] = bs_res
            return classify_deliverable_match(bs_res, version, deliverable_type)

        # 7. Static curated cache (POWER_ECOSYSTEM_CACHE) — covers packages not yet
        #    in any of the live indexes above (e.g. mkl blocker, essl, blis)
        if clean_name in self._cache:
            item = self._cache[clean_name].copy()
            avail_ver = item.get("available_version")
            if avail_ver and version and version != "latest":
                cmp = compare_versions(version, avail_ver)
                if cmp > 0:
                    item["status"] = AvailabilityStatus.UNPORTED_BUILD_REQUIRED
                    item["version_warning"] = (
                        f"Requested version {version} exceeds verified ppc64le version {avail_ver}; source build or backport required."
                    )
                elif cmp < 0:
                    item["version_warning"] = (
                        f"Requested version {version} is older than available ppc64le version {avail_ver}; recommend upgrading."
                    )
            return classify_deliverable_match(item, version, deliverable_type)

        # 8. Standard arch-independent runtime packages
        if ecosystem == "npm":
            raw = {
                "status": AvailabilityStatus.PLATFORM_AGNOSTIC,
                "tier": "Node.js JavaScript package (noarch)",
                "evidence": f"NPM Registry: {clean_name} runs on Node.js ppc64le engine",
                "url": f"https://www.npmjs.com/package/{clean_name}",
            }
            return classify_deliverable_match(raw, version, deliverable_type)
        elif ecosystem == "maven":
            raw = {
                "status": AvailabilityStatus.PLATFORM_AGNOSTIC,
                "tier": "Java bytecode package (noarch)",
                "evidence": f"Maven Central: {clean_name} runs on OpenJDK ppc64le JVM",
                "url": f"https://search.maven.org/artifact/{clean_name}",
            }
            return classify_deliverable_match(raw, version, deliverable_type)

        # 9. Gemini LLM agentic research
        if self.gemini_client:
            llm_res = await self._probe_gemini_llm(clean_name, version, ecosystem, target_os)
            if llm_res:
                self._cache[clean_name] = llm_res
                return classify_deliverable_match(llm_res, version, deliverable_type)

        # 10. Default fallback
        raw = {
            "status": AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
            "tier": "Unverified / Requires Source Build",
            "evidence": f"No immediate pre-built binary verified for {target_os} ppc64le",
            "url": f"https://github.com/search?q={clean_name}+ppc64le",
        }
        return classify_deliverable_match(raw, version, deliverable_type)

    # ------------------------------------------------------------------
    # New source probes (synchronous — read from local index files)
    # ------------------------------------------------------------------

    def _probe_icr_power(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """Check ICR ppc64le-oss catalogue for a named container image.

        The index canonical key strips the trailing '-ppc64le' suffix so that a
        query for 'mongodb' matches 'mongodb-ppc64le', 'opensearch' matches
        'opensearch-ppc64le', etc.  Version matching follows the same
        compare_versions logic used elsewhere: if the requested version is newer
        than any catalogued tag we return None (let live probes try) so as not
        to falsely declare availability.
        """
        lookup = _load_icr_index()
        # Try exact name, then strip -ppc64le suffix, then add it
        candidates = [
            name,
            name.rstrip("-ppc64le"),
            name + "-ppc64le" if not name.endswith("-ppc64le") else name,
        ]
        entries: List[Dict] = []
        for key in candidates:
            if key.lower() in lookup:
                entries = lookup[key.lower()]
                break
        if not entries:
            return None

        # Pick the best matching entry:
        # 1. Exact version match, 2. latest entry (first in list)
        matched = entries[0]
        for e in entries:
            if e.get("tag", "").lstrip("v") == str(version).lstrip("v"):
                matched = e
                break

        avail_tag = matched.get("tag", "latest")
        full_ref  = matched.get("full_ref", f"icr.io/ppc64le-oss/{matched['image_name']}:{avail_tag}")

        # Version guard: if requested > available tag, don't claim it's available
        if version and version != "latest":
            cmp = compare_versions(version, avail_tag.lstrip("v"))
            if cmp > 0:
                return None  # let live Docker Hub / Quay probes try

        result: Dict[str, Any] = {
            "status":            AvailabilityStatus.NATIVE_AVAILABLE,
            "available_version": avail_tag,
            "tier":              "ICR ppc64le-oss Container",
            "evidence":          f"IBM Container Registry ppc64le-oss namespace: {full_ref}",
            "url":               f"https://github.com/seth-priya/ICR-Power-Image-Tracker/blob/main/docs/index.md",
        }
        if version and version != "latest" and avail_tag != version:
            result["version_warning"] = (
                f"Requested version '{version}' not found in ICR; "
                f"latest available ICR tag is '{avail_tag}'. Pull: docker pull {full_ref}"
            )
        logger.info("ICR Power match: %s → %s", name, full_ref)
        return result

    def _probe_devpi_wheels(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """Check the ppc64le/pyeco DevPi wheels index for a Python package.

        This index is built from DevpiWheelsIndex.md in the pyeco repo and
        contains native ppc64le and noarch wheels maintained by the IBM Power
        Python ecosystem team.  No requests are made to devpi.io — the data
        is entirely sourced from the cloned Markdown file.
        """
        lookup = _load_devpi_index()
        pkg = lookup.get(name) or lookup.get(name.replace("-", "_")) or lookup.get(name.replace("_", "-"))
        if not pkg:
            return None

        has_ppc64le = pkg.get("has_ppc64le_wheel", False)
        has_noarch  = pkg.get("has_noarch_wheel", False)
        avail_ver   = pkg.get("latest_ppc64le_version") or pkg.get("latest_noarch_version") or "latest"
        all_vers    = pkg.get("versions", [])

        status = AvailabilityStatus.NATIVE_AVAILABLE if has_ppc64le else (
                 AvailabilityStatus.PLATFORM_AGNOSTIC if has_noarch else None)
        if not status:
            return None

        tier = ("ppc64le/pyeco DevPi — native ppc64le wheel"
                if has_ppc64le else "ppc64le/pyeco DevPi — noarch wheel")

        result: Dict[str, Any] = {
            "status":            status,
            "available_version": avail_ver,
            "tier":              tier,
            "evidence":          (
                f"ppc64le/pyeco DevPi index (cloned from DevpiWheelsIndex.md); "
                f"{len(all_vers)} version(s) available: {', '.join(all_vers[:5])}"
            ),
            "url": "https://github.com/ppc64le/pyeco/blob/main/DevpiWheelsIndex.md",
        }

        # Version comparison
        if version and version != "latest" and avail_ver and avail_ver != "latest":
            # Check if the exact requested version exists in the index
            clean_req = version.split("+")[0]
            if clean_req in all_vers:
                result["available_version"] = clean_req
            else:
                cmp = compare_versions(clean_req, avail_ver)
                if cmp > 0:
                    result["version_warning"] = (
                        f"Requested version {version} not in DevPi index; "
                        f"latest DevPi ppc64le version is {avail_ver}. May require source build."
                    )
                elif cmp < 0:
                    result["version_warning"] = (
                        f"Requested version {version} is older than DevPi ppc64le version {avail_ver}; "
                        f"recommend upgrading."
                    )

        logger.info("DevPi wheels match: %s → %s (%s)", name, avail_ver, status.value)
        return result

    def _probe_build_scripts(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """Check ppc64le/build-scripts for a package with a build_info.json.

        A hit here means the IBM Power porting team has an active build script
        for this package.  Status is NATIVE_AVAILABLE (a build recipe exists),
        not UNPORTED_BUILD_REQUIRED, and the evidence links directly to the
        build script in the repo.
        """
        lookup = _load_build_scripts_index()
        entry = (
            lookup.get(name) or
            lookup.get(name.replace("-", "_")) or
            lookup.get(name.replace("_", "-"))
        )
        if not entry:
            return None

        avail_ver   = (entry.get("version") or "").lstrip("v") or None
        build_url   = entry.get("raw_build_info_url", "https://github.com/ppc64le/build-scripts")
        pkg_dir_url = (
            f"https://github.com/ppc64le/build-scripts/tree/master/{entry.get('package_dir', '')}"
        )

        result: Dict[str, Any] = {
            "status":            AvailabilityStatus.NATIVE_AVAILABLE,
            "available_version": avail_ver,
            "tier":              "ppc64le/build-scripts — active IBM Power build recipe",
            "evidence":          (
                f"IBM ppc64le/build-scripts repo has build_info.json for '{entry.get('package_name', name)}' "
                f"(version {avail_ver or 'unspecified'}). "
                f"Build script: {entry.get('build_script', 'N/A')}"
            ),
            "url": pkg_dir_url,
        }

        if version and version != "latest" and avail_ver:
            cmp = compare_versions(version.lstrip("v"), avail_ver)
            if cmp > 0:
                result["version_warning"] = (
                    f"Requested version {version} is newer than build-scripts version {avail_ver}; "
                    f"build script may need updating."
                )
            elif cmp < 0:
                result["version_warning"] = (
                    f"Requested version {version} is older than build-scripts version {avail_ver}; "
                    f"recommend upgrading to {avail_ver}."
                )

        logger.info("build-scripts match: %s → version=%s", name, avail_ver)
        return result

    async def _probe_rhel_epel(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """Check Fedora Koji (RHEL/EPEL) for a ppc64le RPM build.

        Uses the Fedora Koji XMLRPC API to:
          1. Search for the package by name.
          2. Retrieve the latest successful build.
          3. Confirm a ppc64le RPM exists for that build.

        Returns NATIVE_AVAILABLE if confirmed, None if not found or on error.
        """
        try:
            proxy = xmlrpc.client.ServerProxy(
                "https://koji.fedoraproject.org/kojihub",
                allow_none=True,
            )
            results = await _run_sync(proxy.search, name, "package", "glob")
            if not results:
                return None

            # Pick exact name match first, else first result
            pkg_match = next((r for r in results if r["name"].lower() == name), results[0])
            pkg_id    = pkg_match["id"]
            pkg_name  = pkg_match["name"]

            builds = await _run_sync(
                proxy.listBuilds,
                {"packageID": pkg_id, "state": 1},   # state=1 = COMPLETE
                {"limit": 1, "order": "-build_id"},
            )
            if not builds:
                return None

            build    = builds[0]
            build_id = build["build_id"]
            nvr      = build["nvr"]

            # Confirm ppc64le RPM exists for this build
            rpms = await _run_sync(proxy.listRPMs, {"buildID": build_id, "arch": "ppc64le"})
            if not rpms:
                return None

            # Extract version from NVR (name-version-release)
            avail_ver = build.get("version", "")

            result: Dict[str, Any] = {
                "status":            AvailabilityStatus.NATIVE_AVAILABLE,
                "available_version": avail_ver,
                "tier":              "RHEL/EPEL — Fedora Koji ppc64le RPM",
                "evidence":          f"Fedora Koji build {nvr} has ppc64le RPM(s): {rpms[0]['nvr']}.{rpms[0]['arch']}",
                "url":               f"https://koji.fedoraproject.org/koji/packageinfo?packageID={pkg_id}",
            }

            if version and version != "latest" and avail_ver:
                cmp = compare_versions(version, avail_ver)
                if cmp > 0:
                    result["version_warning"] = (
                        f"Requested version {version} exceeds EPEL/Koji ppc64le version {avail_ver}; "
                        f"source build or newer EPEL release required."
                    )
                elif cmp < 0:
                    result["version_warning"] = (
                        f"Requested version {version} is older than available EPEL ppc64le version {avail_ver}; "
                        f"recommend upgrading."
                    )

            logger.info("RHEL/EPEL Koji match: %s → %s (ppc64le)", name, nvr)
            return result

        except Exception as exc:
            logger.debug("RHEL/EPEL Koji probe error for %s: %s", name, exc)
            return None

    # ------------------------------------------------------------------
    # Existing live-API probes
    # ------------------------------------------------------------------

    async def _probe_quay(self, image_path: str, tag: str) -> Optional[Dict[str, Any]]:
        """Live probe of Quay.io API inspecting multi-arch manifest list for ppc64le."""
        repo_clean = image_path.replace("quay.io/", "")
        tag_clean = tag if tag and tag != "latest" else "latest"

        url = f"https://quay.io/api/v1/repository/{repo_clean}/tag/?limit=10"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    tags_data = resp.json().get("tags", [])
                    target_tags = [t for t in tags_data if t.get("name") == tag_clean] or tags_data[:3]
                    for t in target_tags:
                        manifest_digest = t.get("manifest_digest")
                        if manifest_digest:
                            m_url = f"https://quay.io/api/v1/repository/{repo_clean}/manifest/{manifest_digest}"
                            m_resp = await client.get(m_url)
                            if m_resp.status_code == 200 and "ppc64le" in m_resp.text:
                                tag_name = t.get("name")
                                logger.info(f"Quay.io live match: {repo_clean}:{tag_name} has ppc64le manifest")
                                res = {
                                    "status": AvailabilityStatus.NATIVE_AVAILABLE,
                                    "available_version": tag_name,
                                    "tier": "Official Quay.io Multi-Arch Container",
                                    "evidence": f"Quay.io/{repo_clean}:{tag_name} verified multi-arch (linux/ppc64le)",
                                    "url": f"https://quay.io/repository/{repo_clean}?tab=tags"
                                }
                                if tag and tag != "latest" and tag != tag_name:
                                    cmp = compare_versions(tag, tag_name)
                                    if cmp < 0:
                                        res["version_warning"] = f"Requested tag '{tag}' not verified on Quay.io, but tag '{tag_name}' supports ppc64le; recommend upgrading."
                                return res
        except Exception as e:
            logger.debug(f"Quay.io live probe error for {image_path}: {e}")
        return None

    async def _probe_docker_hub(self, image_path: str, tag: str) -> Optional[Dict[str, Any]]:
        """Live probe of Docker Hub API v2 inspecting multi-arch manifest list for ppc64le."""
        namespace = "library" if "/" not in image_path else image_path.split("/")[0]
        name = image_path if "/" not in image_path else image_path.split("/")[1]
        tag_clean = tag if tag and tag != "latest" else "latest"

        url = f"https://hub.docker.com/v2/repositories/{namespace}/{name}/tags/{tag_clean}"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    images = data.get("images", [])
                    archs = [img.get("architecture") for img in images if img.get("architecture")]
                    if "ppc64le" in archs:
                        logger.info(f"Docker Hub live match: {namespace}/{name}:{tag_clean} has ppc64le")
                        return {
                            "status": AvailabilityStatus.NATIVE_AVAILABLE,
                            "available_version": tag_clean,
                            "tier": "Official Docker Hub Multi-Arch Container",
                            "evidence": f"Docker Hub {namespace}/{name}:{tag_clean} verified multi-arch (linux/ppc64le)",
                            "url": f"https://hub.docker.com/r/{namespace}/{name}"
                        }

                # If specific tag didn't have ppc64le, check if 'latest' tag does
                if tag_clean != "latest":
                    resp_latest = await client.get(f"https://hub.docker.com/v2/repositories/{namespace}/{name}/tags/latest")
                    if resp_latest.status_code == 200:
                        l_images = resp_latest.json().get("images", [])
                        l_archs = [img.get("architecture") for img in l_images if img.get("architecture")]
                        if "ppc64le" in l_archs:
                            logger.info(f"Docker Hub match: {namespace}/{name}:latest has ppc64le while {tag_clean} does not")
                            return {
                                "status": AvailabilityStatus.NATIVE_AVAILABLE,
                                "available_version": "latest",
                                "version_warning": f"Requested tag '{tag_clean}' does not support ppc64le, but 'latest' supports ppc64le; recommend upgrading image tag.",
                                "tier": "Official Docker Hub Multi-Arch Container (Latest)",
                                "evidence": f"Docker Hub {namespace}/{name}:latest verified multi-arch (linux/ppc64le)",
                                "url": f"https://hub.docker.com/r/{namespace}/{name}"
                            }
        except Exception as e:
            logger.debug(f"Docker Hub live probe error for {image_path}: {e}")
        return None

    async def _probe_pypi(self, name: str, version: str) -> Dict[str, Any]:
        """Live probe of PyPI JSON API checking for ppc64le wheels and universal wheels."""
        has_specific_ver = bool(version and version != "latest")
        url = f"https://pypi.org/pypi/{name}/{version}/json" if has_specific_ver else f"https://pypi.org/pypi/{name}/json"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    urls = data.get("urls", [])
                    has_ppc64le = any("ppc64le" in u.get("filename", "") for u in urls)
                    is_pure_py = any("none-any.whl" in u.get("filename", "") for u in urls)
                    avail_ver = data.get("info", {}).get("version", version or "latest")
                    
                    if has_ppc64le:
                        return {
                            "status": AvailabilityStatus.NATIVE_AVAILABLE,
                            "available_version": avail_ver,
                            "tier": "PyPI Native ppc64le Wheel",
                            "evidence": f"PyPI release {avail_ver}: pre-built ppc64le wheel found for {name}",
                            "url": f"https://pypi.org/project/{name}"
                        }
                    elif is_pure_py:
                        return {
                            "status": AvailabilityStatus.PLATFORM_AGNOSTIC,
                            "available_version": avail_ver,
                            "tier": "Pure Python package (noarch)",
                            "evidence": f"Universal wheel (none-any.whl) available for {name} ({avail_ver})",
                            "url": f"https://pypi.org/project/{name}"
                        }
                    else:
                        # If specific version had no ppc64le wheel, check latest release
                        if has_specific_ver:
                            resp_latest = await client.get(f"https://pypi.org/pypi/{name}/json")
                            if resp_latest.status_code == 200:
                                l_data = resp_latest.json()
                                l_urls = l_data.get("urls", [])
                                l_ver = l_data.get("info", {}).get("version", "")
                                if any("ppc64le" in u.get("filename", "") for u in l_urls):
                                    return {
                                        "status": AvailabilityStatus.NATIVE_AVAILABLE,
                                        "available_version": l_ver,
                                        "version_warning": f"Requested version {version} lacks ppc64le wheels, but newer version {l_ver} provides native wheels; recommend upgrading.",
                                        "tier": "PyPI Native ppc64le Wheel (Newer Release)",
                                        "evidence": f"PyPI release {l_ver} has ppc64le wheels",
                                        "url": f"https://pypi.org/project/{name}"
                                    }

                        return {
                            "status": AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
                            "available_version": avail_ver,
                            "tier": "Native C-extension without prebuilt ppc64le wheel",
                            "evidence": "Only sdist (source) or x86/arm wheels found on PyPI",
                            "url": f"https://pypi.org/project/{name}"
                        }
        except Exception as e:
            logger.debug(f"PyPI probe error for {name}: {e}")

        return {
            "status": AvailabilityStatus.PLATFORM_AGNOSTIC,
            "tier": "Python Package (assumed pure script)",
            "evidence": f"Standard PyPI package {name}",
            "url": f"https://pypi.org/project/{name}"
        }

    async def _probe_gemini_llm(self, name: str, version: str, ecosystem: str, target_os: str) -> Optional[Dict[str, Any]]:
        """Invokes Gemini LLM to research and qualify component availability on IBM Power ppc64le."""
        import json
        prompt = (
            f"You are an expert IBM Power (ppc64le) architecture and Linux package qualification specialist.\n"
            f"Evaluate the availability of '{name}' (version: '{version}', ecosystem: '{ecosystem}') for target OS '{target_os}' on IBM Power (ppc64le).\n"
            "Assess whether it exists in:\n"
            "- RHEL BaseOS, AppStream, EPEL 8/9 repositories for ppc64le (e.g. zlib, rocksdb, openssl, libdeflate)\n"
            "- Container registries (Quay.io, Docker Hub, Red Hat Registry) with verified multi-arch linux/ppc64le manifests (e.g. strimzi/kafka)\n"
            "- PyPI wheels for ppc64le or universal pure Python packages\n"
            "- IBM Open-CE or conda-forge ppc64le channels\n"
            "- If it is a proprietary x86 binary (e.g. Intel MKL), identify it as 'blocker' or 'substitute_available' and recommend IBM Power alternatives (e.g. IBM ESSL, OpenBLAS, BLIS).\n"
            "Also indicate the latest available verified version on ppc64le and any version warning if requested version is newer than available.\n"
            "Return ONLY a valid JSON object with the following schema:\n"
            "{\n"
            '  "status": "native_available" | "platform_agnostic" | "substitute_available" | "unported_build_required" | "blocker",\n'
            '  "tier": "string describing tier",\n'
            '  "evidence": "concrete repository, registry, or package source",\n'
            '  "available_version": "version string or null",\n'
            '  "version_warning": "warning string if requested version > available, or null",\n'
            '  "url": "direct verification link (e.g. https://packages.fedoraproject.org/pkgs/<name>/, https://anaconda.org/conda-forge/<name>, https://pypi.org/project/<name>/, https://hub.docker.com/r/..., or official project repository)",\n'
            '  "substitute": "name of recommended alternative or null"\n'
            "}\n"
            "JSON:"
        )
        try:
            resp_text = generate_gemini_content(self.gemini_client, prompt, json_mode=True)
            if resp_text:
                clean = resp_text.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean)
                status_val = parsed.get("status", "").lower()
                status_map = {
                    "native_available": AvailabilityStatus.NATIVE_AVAILABLE,
                    "platform_agnostic": AvailabilityStatus.PLATFORM_AGNOSTIC,
                    "substitute_available": AvailabilityStatus.SUBSTITUTE_AVAILABLE,
                    "unported_build_required": AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
                    "blocker": AvailabilityStatus.BLOCKER
                }
                if status_val in status_map:
                    evidence_str = str(parsed.get("evidence", ""))
                    tier_str = str(parsed.get("tier", "AI Qualified Package"))
                    avail_ver = parsed.get("available_version")
                    ver_warn = parsed.get("version_warning")
                    
                    # Check version comparison if available_version is returned
                    if avail_ver and version and version != "latest" and not ver_warn:
                        cmp = compare_versions(version, avail_ver)
                        if cmp > 0:
                            status_val = "unported_build_required"
                            ver_warn = f"Requested version {version} exceeds verified ppc64le version {avail_ver}; source build required."
                        elif cmp < 0:
                            ver_warn = f"Requested version {version} is older than available ppc64le version {avail_ver}; recommend upgrading."

                    # Smart URL resolution
                    target_url = parsed.get("url")
                    if not target_url or "example.com" in target_url or not target_url.startswith("http"):
                        ev_lower = (evidence_str + " " + tier_str).lower()
                        if "conda" in ev_lower:
                            target_url = f"https://anaconda.org/conda-forge/{name}"
                        elif "epel" in ev_lower or "fedora" in ev_lower or "rhel" in ev_lower:
                            target_url = f"https://packages.fedoraproject.org/pkgs/{name}/"
                        elif "ubuntu" in ev_lower or "debian" in ev_lower:
                            target_url = f"https://packages.ubuntu.com/search?keywords={name}&searchon=names&suite=all&section=all&arch=ppc64el"
                        elif "pypi" in ev_lower or ecosystem == "pypi":
                            target_url = f"https://pypi.org/project/{name}/"
                        elif "quay" in ev_lower or ecosystem == "quay":
                            target_url = f"https://quay.io/repository/{name}"
                        elif "docker" in ev_lower or ecosystem == "container":
                            target_url = f"https://hub.docker.com/search?q={name}"
                        else:
                            target_url = f"https://github.com/search?q={name}"

                    logger.info(f"Gemini LLM availability reasoning for {name}: status={status_val}, url={target_url}")
                    return {
                        "status": status_map[status_val],
                        "tier": tier_str,
                        "evidence": evidence_str or "Gemini AI Qualified via Power/Distro knowledge",
                        "available_version": avail_ver,
                        "version_warning": ver_warn,
                        "url": target_url,
                        "substitute": parsed.get("substitute")
                    }
        except Exception as e:
            logger.warning(f"Gemini LLM availability evaluation failed for {name}: {e}")
        return None
