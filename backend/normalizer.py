import re
import json
from typing import List, Dict, Any, Tuple


class UniversalNormalizer:
    """Parses various input formats into a standardized list of (package_name, version, ecosystem)."""

    @classmethod
    def normalize(cls, raw_input: str, manifest_type: str = "auto") -> List[Dict[str, str]]:
        if not raw_input or not raw_input.strip():
            return []

        raw_trimmed = raw_input.strip()

        # Try auto-detection if manifest_type is "auto"
        if manifest_type == "auto":
            manifest_type = cls._detect_type(raw_trimmed)

        if manifest_type == "sbom":
            return cls._parse_sbom(raw_trimmed)
        elif manifest_type == "dockerfile":
            return cls._parse_dockerfile(raw_trimmed)
        elif manifest_type == "requirements":
            return cls._parse_requirements(raw_trimmed)
        elif manifest_type == "package_json":
            return cls._parse_package_json(raw_trimmed)
        elif manifest_type == "pom_xml":
            return cls._parse_pom_xml(raw_trimmed)
        else:
            return cls._parse_freeform_text(raw_trimmed)

    @classmethod
    def _detect_type(cls, text: str) -> str:
        text_lower = text.lower()
        if text.startswith("{") and ("bomformat" in text_lower or "spdxversion" in text_lower or "components" in text_lower):
            return "sbom"
        if "from " in text or "docker-compose" in text_lower or "services:" in text_lower:
            return "dockerfile"
        if text.startswith("{") and "dependencies" in text_lower:
            return "package_json"
        if "<project" in text and "<dependencies>" in text:
            return "pom_xml"
        if re.search(r"^[a-zA-Z0-9_\-\.]+\s*([=><!~]=?\s*[0-9\.\*]+)?$", text, re.MULTILINE):
            return "requirements"
        return "text"

    @classmethod
    def _parse_sbom(cls, text: str) -> List[Dict[str, str]]:
        results = []
        try:
            data = json.loads(text)
            # CycloneDX
            if "components" in data:
                for comp in data["components"]:
                    name = comp.get("name")
                    version = comp.get("version", "latest")
                    c_type = comp.get("type", "library")
                    purl = comp.get("purl", "")
                    
                    eco = "native_c"
                    if "pkg:pypi" in purl:
                        eco = "pypi"
                    elif "pkg:npm" in purl:
                        eco = "npm"
                    elif "pkg:maven" in purl:
                        eco = "maven"
                    elif "pkg:rpm" in purl or "pkg:deb" in purl:
                        eco = "rpm"
                    elif "container" in c_type or "oci" in purl or "docker" in purl:
                        eco = "container"

                    if name:
                        results.append({"name": name, "version": version, "ecosystem": eco})
            # SPDX
            elif "packages" in data:
                for pkg in data["packages"]:
                    name = pkg.get("name")
                    version = pkg.get("versionInfo", "latest")
                    if name:
                        results.append({"name": name, "version": version, "ecosystem": "rpm"})
        except Exception:
            return cls._parse_freeform_text(text)

        return results if results else cls._parse_freeform_text(text)

    @classmethod
    def _parse_dockerfile(cls, text: str) -> List[Dict[str, str]]:
        results = []
        # FROM images
        from_matches = re.findall(r"^\s*FROM\s+([^\s]+)", text, re.IGNORECASE | re.MULTILINE)
        for img in from_matches:
            if "--platform" in img:
                continue
            parts = img.split(":")
            name = parts[0]
            version = parts[1] if len(parts) > 1 else "latest"
            results.append({"name": name, "version": version, "ecosystem": "container"})

        # RUN apt-get install / yum install / dnf install
        pkg_installs = re.findall(r"(?:apt-get|yum|dnf|apk)\s+(?:-y\s+)?install\s+([^;&\n]+)", text, re.IGNORECASE)
        for line in pkg_installs:
            pkgs = [p.strip() for p in line.split() if p.strip() and not p.startswith("-")]
            for p in pkgs:
                parts = p.split("=")
                name = parts[0]
                version = parts[1] if len(parts) > 1 else "latest"
                results.append({"name": name, "version": version, "ecosystem": "rpm"})

        # pip install in dockerfile
        pip_installs = re.findall(r"pip\s+install\s+([^;&\n]+)", text, re.IGNORECASE)
        for line in pip_installs:
            pkgs = [p.strip() for p in line.split() if p.strip() and not p.startswith("-")]
            for p in pkgs:
                name, version = cls._clean_version(p)
                results.append({"name": name, "version": version, "ecosystem": "pypi"})

        return results if results else cls._parse_freeform_text(text)

    @classmethod
    def _parse_requirements(cls, text: str) -> List[Dict[str, str]]:
        results = []
        lines = text.strip().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name, version = cls._clean_version(line)
            if name:
                results.append({"name": name, "version": version, "ecosystem": "pypi"})
        return results

    @classmethod
    def _parse_package_json(cls, text: str) -> List[Dict[str, str]]:
        results = []
        try:
            data = json.loads(text)
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            for name, ver in deps.items():
                clean_ver = ver.replace("^", "").replace("~", "").replace(">", "").strip()
                results.append({"name": name, "version": clean_ver or "latest", "ecosystem": "npm"})
        except Exception:
            return cls._parse_freeform_text(text)
        return results

    @classmethod
    def _parse_pom_xml(cls, text: str) -> List[Dict[str, str]]:
        results = []
        artifact_matches = re.findall(r"<artifactId>([^<]+)</artifactId>", text)
        version_matches = re.findall(r"<version>([^<]+)</version>", text)
        for i, art in enumerate(artifact_matches):
            ver = version_matches[i] if i < len(version_matches) else "latest"
            results.append({"name": art.strip(), "version": ver.strip(), "ecosystem": "maven"})
        return results

    @classmethod
    def _parse_freeform_text(cls, text: str) -> List[Dict[str, str]]:
        """Extracts recognizable packages from human sentences, lists, or notes."""
        results = []
        
        # Common tech keywords to look for
        known_tokens = [
            "nginx", "redis", "postgres", "postgresql", "mysql", "mongodb", "kafka", "rabbitmq",
            "elasticsearch", "opensearch", "torch", "pytorch", "tensorflow", "scipy", "numpy",
            "pandas", "onnxruntime", "grpc", "rocksdb", "leveldb", "fastapi", "flask", "django",
            "express", "spring-boot", "golang", "rust", "llvm", "bazel", "cmake", "libdeflate",
            "openssl", "zlib", "simdjson", "spdk", "dpdk", "arrow", "parquet", "faiss",
            "intel-mkl", "mkl", "openblas", "blis", "essl", "snappy", "lz4"
        ]
        
        text_lower = text.lower()
        found_names = set()

        for token in known_tokens:
            if re.search(rf"\b{re.escape(token)}\b", text_lower):
                # Guess ecosystem
                eco = "container"
                if token in ["torch", "pytorch", "tensorflow", "scipy", "numpy", "pandas", "fastapi", "flask", "django"]:
                    eco = "pypi"
                elif token in ["nginx", "redis", "postgres", "postgresql", "mysql", "mongodb", "kafka", "rabbitmq"]:
                    eco = "container"
                elif token in ["rocksdb", "leveldb", "simdjson", "spdk", "dpdk", "libdeflate", "openssl", "faiss", "zlib", "intel-mkl", "mkl", "openblas", "blis", "essl", "snappy", "lz4"]:
                    eco = "native_c"

                # Look for adjacent version like "torch 2.1" or "nginx:1.24"
                ver_match = re.search(rf"{re.escape(token)}[:\s/v]+([0-9]+\.[0-9]+(\.[0-9]+)?)", text_lower)
                ver = ver_match.group(1) if ver_match else "latest"

                results.append({"name": token, "version": ver, "ecosystem": eco})
                found_names.add(token)

        # Also capture line-by-line simple name==version or name:version
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([a-zA-Z0-9_\-\.]+)[=:\s]+([0-9\.\*]+[a-zA-Z0-9_\-\.]*)", line)
            if match:
                name, ver = match.group(1), match.group(2)
                if name.lower() not in found_names:
                    results.append({"name": name, "version": ver, "ecosystem": "container" if ":" in line else "pypi"})
                    found_names.add(name.lower())

        # If nothing matched, treat lines as arbitrary packages
        if not results:
            for line in text.splitlines():
                clean = line.strip().strip("-*1234567890. ")
                if clean and len(clean) > 2 and " " not in clean:
                    results.append({"name": clean, "version": "latest", "ecosystem": "native_c"})

        return results

    @staticmethod
    def _clean_version(spec: str) -> Tuple[str, str]:
        for op in ["==", ">=", "<=", "~=", ">", "<"]:
            if op in spec:
                parts = spec.split(op)
                return parts[0].strip(), parts[1].strip()
        return spec.strip(), "latest"
