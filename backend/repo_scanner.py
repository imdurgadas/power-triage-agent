import os
import re
import shutil
import tempfile
import logging
from typing import Dict, Any, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None
from .models import (
    ArchSupportScan,
    DockerfileImageFinding,
    ConfigImageFinding,
    AvailabilityStatus,
)
from .gemini_helper import generate_gemini_content

logger = logging.getLogger("repo_scanner")

# Standard regexes for base images in Dockerfiles: FROM [--platform=...] <image>[:tag] [AS <stage>]
DOCKERFILE_FROM_RE = re.compile(
    r"^\s*FROM\s+(?:--platform=[^\s]+\s+)?([^\s:]+)(?::([^\s]+))?(?:\s+[aA][sS]\s+([^\s]+))?",
    re.IGNORECASE | re.MULTILINE
)

# Architecture indicators
PPC64LE_MARKERS = [
    r"__powerpc__",
    r"__ppc64__",
    r"_ARCH_PPC",
    r"ppc64le",
    r"altivec",
    r"__VSX__",
    r"linux/ppc64le",
    r"powerpc64le"
]

X86_ONLY_MARKERS = [
    r"__x86_64__",
    r"__i386__",
    r"_M_X64",
    r"immintrin\.h",
    r"emmintrin\.h",
    r"xmmintrin\.h",
    r"linux/amd64"
]


class RepoScanner:
    """Scans repositories (local directory or shallow Git clone) for:
    - Architecture support markers in build configs, C/C++ source, and CI workflows (Sub-Task 6)
    - Dockerfiles and base container images (Sub-Task 5)
    - Compose, Kubernetes, and CI workflow YAMLs referencing container images (Sub-Task 7)
    """

    @classmethod
    def shallow_clone_repo(cls, git_url: str, depth: int = 1) -> Optional[str]:
        """Performs a temporary shallow git clone. Returns temporary directory path or None."""
        if not git_url or not (git_url.startswith("http://") or git_url.startswith("https://") or git_url.startswith("git@")):
            return None

        temp_dir = tempfile.mkdtemp(prefix="ppc_triage_repo_")
        cmd = f"git clone --depth {depth} {git_url} {temp_dir}"
        logger.info(f"Cloning repository shallowly: {git_url}")
        try:
            ret = os.system(f"{cmd} > /dev/null 2>&1")
            if ret == 0:
                return temp_dir
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None
        except Exception as e:
            logger.warning(f"Git clone failed for {git_url}: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

    @classmethod
    def cleanup_repo(cls, repo_dir: Optional[str]):
        """Safely cleans up temporary clone directory."""
        if repo_dir and os.path.exists(repo_dir) and "ppc_triage_repo_" in repo_dir:
            shutil.rmtree(repo_dir, ignore_errors=True)

    @classmethod
    def scan_arch_support(cls, root_path: str) -> ArchSupportScan:
        """Inspects source files, CMake/Makefiles, and CI workflows for ppc64le and x86 markers."""
        ppc_hits = set()
        x86_hits = set()
        ci_matrix_has_power = False

        scan_extensions = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".cmake", ".txt", ".yml", ".yaml", ".sh", "Makefile"}
        ci_dir = os.path.join(root_path, ".github", "workflows")
        
        # Check CI directory specifically
        if os.path.isdir(ci_dir):
            for fname in os.listdir(ci_dir):
                if fname.endswith((".yml", ".yaml")):
                    fpath = os.path.join(ci_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            ci_content = f.read().lower()
                            if "ppc64le" in ci_content or "powerpc" in ci_content:
                                ci_matrix_has_power = True
                                ppc_hits.add(f".github/workflows/{fname}: ppc64le matrix runner")
                    except Exception:
                        pass

        # Scan repository files (capped at 500 files for responsiveness)
        file_count = 0
        for root, dirs, files in os.walk(root_path):
            # Skip hidden, git, and node_modules directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "vendor", "build", "dist"]]
            for file in files:
                file_count += 1
                if file_count > 500:
                    break
                ext = os.path.splitext(file)[1].lower()
                if ext in scan_extensions or file in ["Makefile", "CMakeLists.txt", "Dockerfile"]:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, root_path)
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read(65536)  # Read up to 64KB per file
                            for pat in PPC64LE_MARKERS:
                                if re.search(pat, content, re.IGNORECASE):
                                    ppc_hits.add(f"{rel_path}: matches {pat}")
                            for pat in X86_ONLY_MARKERS:
                                if re.search(pat, content, re.IGNORECASE):
                                    x86_hits.add(f"{rel_path}: matches {pat}")
                    except Exception:
                        pass
            if file_count > 500:
                break

        # Compute effort adjustment factor
        # If active ppc64le CI / upstream support exists, discount effort (e.g. 0.7x or 0.8x)
        # If exclusively x86 markers without any Power awareness, increase effort (e.g. 1.3x)
        has_ppc = len(ppc_hits) > 0 or ci_matrix_has_power
        has_x86 = len(x86_hits) > 0

        if ci_matrix_has_power:
            adj = 0.7  # Upstream already tests ppc64le in CI
        elif has_ppc and not has_x86:
            adj = 0.8  # Power-friendly codebase
        elif has_ppc and has_x86:
            adj = 1.0  # Multi-arch conditional codebase
        elif has_x86 and not has_ppc:
            adj = 1.3  # Hardcoded x86 assumptions
        else:
            adj = 1.0  # Neutral / agnostic

        return ArchSupportScan(
            ppc64le_markers_found=sorted(list(ppc_hits))[:10],
            x86_only_markers_found=sorted(list(x86_hits))[:10],
            ci_matrix_has_power=ci_matrix_has_power,
            scan_source="git_repository",
            effort_adjustment_factor=adj
        )

    @classmethod
    def llm_infer_arch_support(cls, package_name: str, gemini_client=None) -> ArchSupportScan:
        """Infers repository architecture posture using Gemini when no git repo URL is provided."""
        if not gemini_client:
            return ArchSupportScan(scan_source="default_heuristic")

        prompt = (
            f"Evaluate upstream architectural support for package '{package_name}' on IBM Power (ppc64le).\n"
            "Does upstream repository contain IBM Power/VSX code, CI runners (GitHub Actions/Travis for ppc64le), "
            "or does it have hardcoded x86 SSE/AVX intrinsics without Power alternatives?\n"
            "Respond ONLY with a JSON object with this schema:\n"
            "{\n"
            '  "ppc64le_markers": ["list of known Power features/patches or empty"],\n'
            '  "x86_only_markers": ["list of x86-only dependencies or empty"],\n'
            '  "ci_matrix_has_power": true | false,\n'
            '  "effort_adjustment_factor": float (0.7 for strong upstream Power CI/code, 1.0 for neutral, 1.3 for hardcoded x86)\n'
            "}\n"
            "JSON:"
        )
        try:
            import json
            resp = generate_gemini_content(gemini_client, prompt, json_mode=True)
            if resp:
                clean = resp.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean)
                return ArchSupportScan(
                    ppc64le_markers_found=data.get("ppc64le_markers", []),
                    x86_only_markers_found=data.get("x86_only_markers", []),
                    ci_matrix_has_power=bool(data.get("ci_matrix_has_power", False)),
                    scan_source="llm_inference",
                    effort_adjustment_factor=float(data.get("effort_adjustment_factor", 1.0))
                )
        except Exception as e:
            logger.warning(f"LLM arch support inference failed for {package_name}: {e}")

        return ArchSupportScan(scan_source="llm_fallback")

    @classmethod
    def scan_dockerfiles(cls, root_path: str) -> List[DockerfileImageFinding]:
        """Discovers all Dockerfiles in repository and parses FROM base images."""
        findings = []
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "vendor"]]
            for file in files:
                if file == "Dockerfile" or file.startswith("Dockerfile.") or file.endswith(".dockerfile"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, root_path)
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                            for line in lines:
                                match = DOCKERFILE_FROM_RE.match(line)
                                if match:
                                    image = match.group(1).strip()
                                    tag = match.group(2) or "latest"
                                    stage = match.group(3)
                                    # Ignore local stage references (e.g. FROM builder AS runner)
                                    if any(f.stage_name == image for f in findings if f.stage_name):
                                        continue
                                    findings.append(DockerfileImageFinding(
                                        dockerfile_path=rel_path,
                                        base_image=image,
                                        tag=tag,
                                        stage_name=stage,
                                        status=AvailabilityStatus.NATIVE_AVAILABLE
                                    ))
                    except Exception as e:
                        logger.debug(f"Failed parsing Dockerfile {full_path}: {e}")
        return findings

    @classmethod
    def scan_config_images(cls, root_path: str) -> List[ConfigImageFinding]:
        """Discovers container images in docker-compose.yml, k8s manifests, and CI workflows."""
        findings = []
        target_files = []
        
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "vendor"]]
            for file in files:
                lower = file.lower()
                if lower in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
                    target_files.append((os.path.join(root, file), "docker-compose"))
                elif ".github/workflows" in root and lower.endswith((".yml", ".yaml")):
                    target_files.append((os.path.join(root, file), "ci_workflow"))
                elif lower.endswith((".k8s.yml", ".k8s.yaml", ".deployment.yml", ".deployment.yaml")):
                    target_files.append((os.path.join(root, file), "kubernetes"))

        for full_path, file_type in target_files:
            rel_path = os.path.relpath(full_path, root_path)
            parsed_with_yaml = False
            if yaml:
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        docs = yaml.safe_load_all(f)
                        for doc in docs:
                            if not isinstance(doc, dict):
                                continue
                            cls._extract_yaml_images(doc, rel_path, file_type, findings)
                    parsed_with_yaml = True
                except Exception:
                    parsed_with_yaml = False

            if not parsed_with_yaml:
                # Fallback to regex line scanning if YAML parsing fails or pyyaml is not installed
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line_str = line.strip()
                            if line_str.startswith("image:"):
                                img_val = line_str.split("image:", 1)[1].strip().strip("\"'")
                                if img_val and not img_val.startswith("${"):
                                    findings.append(ConfigImageFinding(
                                        config_file_path=rel_path,
                                        config_file_type=file_type,
                                        image_ref=img_val,
                                        status=AvailabilityStatus.NATIVE_AVAILABLE
                                    ))
                except Exception:
                    pass

        return findings

    @classmethod
    def _extract_yaml_images(cls, obj: Any, rel_path: str, file_type: str, findings: List[ConfigImageFinding]):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "image" and isinstance(v, str) and not v.startswith("${"):
                    findings.append(ConfigImageFinding(
                        config_file_path=rel_path,
                        config_file_type=file_type,
                        image_ref=v,
                        status=AvailabilityStatus.NATIVE_AVAILABLE
                    ))
                elif isinstance(v, (dict, list)):
                    cls._extract_yaml_images(v, rel_path, file_type, findings)
        elif isinstance(obj, list):
            for item in obj:
                cls._extract_yaml_images(item, rel_path, file_type, findings)
