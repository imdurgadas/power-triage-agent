import re
import logging
from typing import List, Dict, Any, Tuple, Optional
import httpx
from bs4 import BeautifulSoup

from .gemini_helper import generate_gemini_content

logger = logging.getLogger("url_extractor")


class URLExtractor:
    """Extracts software packages, dependencies, and versions from GitHub repositories or documentation/package websites."""

    URL_REGEX = re.compile(
        r"^(https?://)?(www\.)?([a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,})(/.*)?$",
        re.IGNORECASE
    )

    @classmethod
    def is_url(cls, text: str) -> bool:
        if not text:
            return False
        trimmed = text.strip()
        # Single-line URL check
        if "\n" in trimmed:
            return False
        return bool(re.match(r"^https?://[^\s]+$", trimmed))

    @classmethod
    async def extract_from_url(
        cls,
        url: str,
        gemini_client: Optional[Any] = None
    ) -> Tuple[List[Dict[str, str]], str, str]:
        """Fetches URL, extracts text/manifests, and infers dependencies using Gemini LLM or heuristics.
        
        Returns:
            (packages, page_title, summary_note)
        """
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        logger.info(f"Extracting package specifications from URL: {url}")
        
        content_text = ""
        page_title = url
        is_github = "github.com" in url.lower()

        # Step 1: Fetch Content
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7"
                }

                if is_github:
                    content_text, page_title = await cls._fetch_github_repo_content(client, url)
                else:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        # Remove script, style, nav, footer tags
                        for tag in soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        
                        if soup.title and soup.title.string:
                            page_title = soup.title.string.strip()
                        
                        # Extract main body text
                        content_text = soup.get_text(separator="\n", strip=True)
                        # Keep first 8000 characters to fit context cleanly
                        content_text = content_text[:8000]
                    else:
                        logger.warning(f"Failed to fetch URL {url} (status {resp.status_code})")
        except Exception as e:
            logger.warning(f"Error fetching URL {url}: {e}")

        # Step 2: Extract Dependencies (LLM or Heuristic)
        packages: List[Dict[str, str]] = []
        if gemini_client and content_text:
            packages = cls._infer_with_gemini(gemini_client, url, page_title, content_text)

        # Fallback to heuristic extraction if LLM is not configured or returned empty
        if not packages:
            packages = cls._infer_with_heuristics(url, content_text)

        summary_note = f"Extracted {len(packages)} component(s) from {url} ({page_title})"
        return packages, page_title, summary_note

    @classmethod
    async def _fetch_github_repo_content(cls, client: httpx.AsyncClient, url: str) -> Tuple[str, str]:
        """Inspects GitHub repository for manifests like requirements.txt, package.json, CMakeLists.txt, Dockerfile, or README."""
        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if not match:
            return "", url

        owner = match.group(1)
        repo = match.group(2).replace(".git", "")
        repo_title = f"{owner}/{repo}"

        branches = ["main", "master"]
        manifest_files = [
            ("requirements.txt", "pypi"),
            ("package.json", "npm"),
            ("CMakeLists.txt", "native_c"),
            ("Dockerfile", "container"),
            ("pom.xml", "maven"),
            ("README.md", "text"),
        ]

        aggregated_text = f"GitHub Repository: {owner}/{repo}\n"

        for branch in branches:
            for filename, _ in manifest_files:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filename}"
                try:
                    resp = await client.get(raw_url, timeout=5.0)
                    if resp.status_code == 200 and resp.text:
                        aggregated_text += f"\n--- File: {filename} ({branch}) ---\n"
                        aggregated_text += resp.text[:3000] + "\n"
                        # If we found direct manifests, we got good data
                        if filename != "README.md":
                            break
                except Exception:
                    continue

        return aggregated_text, repo_title

    @classmethod
    def _infer_with_gemini(
        cls,
        gemini_client: Any,
        url: str,
        title: str,
        content: str
    ) -> List[Dict[str, str]]:
        """Uses Gemini to intelligently extract packages, dependencies, and versions."""
        prompt = (
            f"You are an expert systems architecture and software dependency analyst.\n"
            f"A user wants to migrate a workload or library from this URL to IBM Power (ppc64le):\n"
            f"URL: {url}\n"
            f"Page Title: {title}\n"
            f"Content snippet:\n{content[:4000]}\n\n"
            "Task: Identify the primary software component and all its essential build, runtime, and third-party dependencies with their versions.\n"
            "Infer appropriate ecosystems from: 'container', 'pypi', 'npm', 'maven', 'rpm', 'native_c'.\n"
            "Return ONLY a JSON array of objects with keys 'name', 'version', and 'ecosystem'. E.g.:\n"
            "[\n"
            '  {"name": "rocksdb", "version": "8.6", "ecosystem": "native_c"},\n'
            '  {"name": "snappy", "version": "1.1.9", "ecosystem": "native_c"}\n'
            "]\n"
            "JSON:"
        )
        try:
            resp_text = generate_gemini_content(gemini_client, prompt, json_mode=True)
            if resp_text:
                import json
                cleaned = resp_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned)
                if isinstance(data, list):
                    valid = []
                    for item in data:
                        if isinstance(item, dict) and item.get("name"):
                            valid.append({
                                "name": str(item["name"]).strip(),
                                "version": str(item.get("version", "latest")).strip() or "latest",
                                "ecosystem": str(item.get("ecosystem", "container")).strip()
                            })
                    return valid
        except Exception as e:
            logger.warning(f"Gemini URL dependency inference failed: {e}")

        return []

    @classmethod
    def _infer_with_heuristics(cls, url: str, content: str) -> List[Dict[str, str]]:
        """Intelligent heuristic and regex extraction for offline / simulation mode."""
        url_lower = url.lower()
        content_lower = content.lower()
        results: List[Dict[str, str]] = []
        seen = set()

        def add_pkg(name: str, ver: str = "latest", eco: str = "native_c"):
            k = name.lower()
            if k not in seen:
                seen.add(k)
                results.append({"name": name, "version": ver, "ecosystem": eco})

        # Curated project domain patterns
        if "rocksdb" in url_lower:
            add_pkg("rocksdb", "8.6", "native_c")
            add_pkg("snappy", "1.1.9", "native_c")
            add_pkg("zlib", "1.2.11", "native_c")
            add_pkg("lz4", "1.9.4", "native_c")
            add_pkg("jemalloc", "5.3.0", "native_c")
            return results

        if "redis" in url_lower:
            add_pkg("redis", "7.2", "container")
            add_pkg("jemalloc", "5.3.0", "native_c")
            return results

        if "fastapi" in url_lower:
            add_pkg("fastapi", "0.110.0", "pypi")
            add_pkg("pydantic", "2.6.0", "pypi")
            add_pkg("uvicorn", "0.28.0", "pypi")
            return results

        if "pytorch" in url_lower or "torch" in url_lower:
            add_pkg("torch", "2.1.0", "pypi")
            add_pkg("numpy", "1.26.0", "pypi")
            add_pkg("scipy", "1.11.0", "pypi")
            return results

        if "nginx" in url_lower:
            add_pkg("nginx", "1.24", "container")
            add_pkg("openssl", "3.0", "native_c")
            return results

        if "simdjson" in url_lower:
            add_pkg("simdjson", "3.6", "native_c")
            return results

        # Generic GitHub repo name deduction: https://github.com/owner/repo
        github_match = re.search(r"github\.com/[^/]+/([^/\s?#]+)", url)
        if github_match:
            repo_name = github_match.group(1).replace(".git", "").lower()
            add_pkg(repo_name, "latest", "native_c")

        # Scan text for common technology patterns
        known_tokens = [
            ("nginx", "container"), ("redis", "container"), ("postgres", "container"),
            ("postgresql", "container"), ("kafka", "container"), ("torch", "pypi"),
            ("pytorch", "pypi"), ("tensorflow", "pypi"), ("numpy", "pypi"),
            ("scipy", "pypi"), ("pandas", "pypi"), ("fastapi", "pypi"),
            ("rocksdb", "native_c"), ("simdjson", "native_c"), ("snappy", "native_c"),
            ("zlib", "native_c"), ("openssl", "native_c"), ("jemalloc", "native_c")
        ]

        for token, eco in known_tokens:
            if re.search(rf"\b{re.escape(token)}\b", content_lower):
                ver_match = re.search(rf"{re.escape(token)}[:\s/v=]+([0-9]+\.[0-9]+(\.[0-9]+)?)", content_lower)
                ver = ver_match.group(1) if ver_match else "latest"
                add_pkg(token, ver, eco)

        # Fallback if nothing extracted: treat repo or domain as package
        if not results:
            domain_match = re.search(r"https?://(?:www\.)?([^/\.]+)", url)
            if domain_match:
                pkg_name = domain_match.group(1)
                add_pkg(pkg_name, "latest", "native_c")

        return results
