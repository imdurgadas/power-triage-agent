import re
import httpx
import logging
from typing import Dict, Any, Optional, Tuple
from .models import AvailabilityStatus
from .gemini_helper import generate_gemini_content

logger = logging.getLogger("prober")


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
        "available_version": "1.1.9",
        "tier": "Core OS Library",
        "evidence": "RHEL 8/9 AppStream ppc64le",
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
    "torch": {
        "status": AvailabilityStatus.SUBSTITUTE_AVAILABLE,
        "tier": "IBM Open-CE optimized package",
        "evidence": "IBM Open-CE / RocketCE repository (conda-forge ppc64le)",
        "url": "https://github.com/open-ce/open-ce",
        "substitute": "open-ce/pytorch-ppc64le (optimized with Power VSX / MMA)"
    },
    "pytorch": {
        "status": AvailabilityStatus.SUBSTITUTE_AVAILABLE,
        "tier": "IBM Open-CE optimized package",
        "evidence": "IBM Open-CE / RocketCE repository (conda-forge ppc64le)",
        "url": "https://github.com/open-ce/open-ce",
        "substitute": "open-ce/pytorch-ppc64le (optimized with Power VSX / MMA)"
    },
    "tensorflow": {
        "status": AvailabilityStatus.SUBSTITUTE_AVAILABLE,
        "tier": "IBM Open-CE optimized package",
        "evidence": "IBM Open-CE channel (ppc64le builds)",
        "url": "https://github.com/open-ce/open-ce",
        "substitute": "open-ce/tensorflow-ppc64le"
    },
    "fastapi": {"status": AvailabilityStatus.PLATFORM_AGNOSTIC, "tier": "Pure Python package (noarch)", "evidence": "PyPI (py2.py3-none-any.whl)", "url": "https://pypi.org/project/fastapi"},
    "flask": {"status": AvailabilityStatus.PLATFORM_AGNOSTIC, "tier": "Pure Python package (noarch)", "evidence": "PyPI (py2.py3-none-any.whl)", "url": "https://pypi.org/project/flask"},
    "requests": {"status": AvailabilityStatus.PLATFORM_AGNOSTIC, "tier": "Pure Python package (noarch)", "evidence": "PyPI (py2.py3-none-any.whl)", "url": "https://pypi.org/project/requests"},
    "pydantic": {"status": AvailabilityStatus.NATIVE_AVAILABLE, "tier": "PyPI native ppc64le wheel", "evidence": "PyPI release (pydantic-core ppc64le wheel)", "url": "https://pypi.org/project/pydantic"},

    # Unported or complex native components that require building from source
    "rocksdb": {
        "status": AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
        "tier": "Requires build from source",
        "evidence": "No prebuilt RPM/binary for RHEL ppc64le in default repo",
        "url": "https://github.com/facebook/rocksdb",
        "build_system": "CMake / Make"
    },
    "simdjson": {
        "status": AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
        "tier": "Requires build from source & AVX fallback",
        "evidence": "Source build required; has fallback scalar/Altivec path",
        "url": "https://github.com/simdjson/simdjson",
        "build_system": "CMake"
    },
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


class MultiSourceProber:
    """Probes Docker Hub, Quay.io, PyPI, and Linux Distro repositories using live APIs and Gemini LLM reasoning."""

    def __init__(self, gemini_client=None):
        self._cache = POWER_ECOSYSTEM_CACHE.copy()
        self.gemini_client = gemini_client

    def set_gemini_client(self, client):
        self.gemini_client = client

    async def probe_component(self, name: str, version: str = "latest", ecosystem: str = "container", target_os: str = "rhel9") -> Dict[str, Any]:
        norm_name = name.lower().strip()
        
        # Clean image prefixes if container
        clean_name = norm_name
        if clean_name.startswith("quay.io/"):
            clean_name = clean_name.replace("quay.io/", "")
            ecosystem = "quay"
        elif clean_name.startswith("docker.io/"):
            clean_name = clean_name.replace("docker.io/", "")

        # 1. Check local curated cache
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
            return item

        # 2. Live API check for container registries
        if ecosystem in ["container", "docker", "quay"] or "/" in clean_name:
            # Check Quay.io if it's from quay or named like strimzi/kafka
            if ecosystem == "quay" or "strimzi" in clean_name or "redhat" in clean_name:
                quay_res = await self._probe_quay(clean_name, version)
                if quay_res and quay_res.get("status") == AvailabilityStatus.NATIVE_AVAILABLE:
                    self._cache[clean_name] = quay_res
                    return quay_res

            # Check Docker Hub live API
            docker_res = await self._probe_docker_hub(clean_name, version)
            if docker_res and docker_res.get("status") == AvailabilityStatus.NATIVE_AVAILABLE:
                self._cache[clean_name] = docker_res
                return docker_res

        # 3. Live API check for PyPI
        if ecosystem == "pypi":
            pypi_res = await self._probe_pypi(clean_name, version)
            if pypi_res and pypi_res.get("status") in [AvailabilityStatus.NATIVE_AVAILABLE, AvailabilityStatus.PLATFORM_AGNOSTIC]:
                self._cache[clean_name] = pypi_res
                return pypi_res

        # 4. Standard runtime packages
        if ecosystem == "npm":
            return {
                "status": AvailabilityStatus.PLATFORM_AGNOSTIC,
                "tier": "Node.js JavaScript package (noarch)",
                "evidence": f"NPM Registry: {clean_name} runs on Node.js ppc64le engine",
                "url": f"https://www.npmjs.com/package/{clean_name}"
            }
        elif ecosystem == "maven":
            return {
                "status": AvailabilityStatus.PLATFORM_AGNOSTIC,
                "tier": "Java bytecode package (noarch)",
                "evidence": f"Maven Central: {clean_name} runs on OpenJDK ppc64le JVM",
                "url": f"https://search.maven.org/artifact/{clean_name}"
            }

        # 5. Agentic AI Layer: Use Gemini LLM to research availability across RHEL/EPEL/Quay/Docker/Power ecosystem
        if self.gemini_client:
            llm_res = await self._probe_gemini_llm(clean_name, version, ecosystem, target_os)
            if llm_res:
                self._cache[clean_name] = llm_res
                return llm_res

        # 6. Default fallback for unlisted native packages
        return {
            "status": AvailabilityStatus.UNPORTED_BUILD_REQUIRED,
            "tier": "Unverified / Requires Source Build",
            "evidence": f"No immediate pre-built binary verified for {target_os} ppc64le",
            "url": f"https://github.com/search?q={clean_name}+ppc64le"
        }

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
