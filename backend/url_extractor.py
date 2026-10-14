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
        gemini_client: Optional[Any] = None,
        llm_service: Optional[Any] = None,
    ) -> Tuple[List[Dict[str, str]], str, str]:
        """Fetches URL, extracts text/manifests, and infers dependencies using LLM (IBM Bob or Gemini) or heuristics.
        
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
        if (llm_service or gemini_client) and content_text:
            packages = cls._infer_with_gemini(gemini_client, url, page_title, content_text, llm_service=llm_service)

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
        content: str,
        llm_service: Optional[Any] = None,
    ) -> List[Dict[str, str]]:
        """Uses LLM (IBM Bob or Gemini) to intelligently extract packages, dependencies, and versions."""
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
            '  {"name": "component_name", "version": "1.0.0", "ecosystem": "native_c"},\n'
            '  {"name": "sub_dependency", "version": "2.1.0", "ecosystem": "native_c"}\n'
            "]\n"
            "JSON:"
        )
        try:
            if llm_service and hasattr(llm_service, "generate_content"):
                resp_text = llm_service.generate_content(prompt, json_mode=True, stage="Manifest URL Inference")
            elif gemini_client:
                resp_text = generate_gemini_content(gemini_client, prompt, json_mode=True)
            else:
                resp_text = None

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
            logger.warning(f"LLM URL dependency inference failed: {e}")

        return []

    @classmethod
    def _infer_with_heuristics(cls, url: str, content: str) -> List[Dict[str, str]]:
        """Intelligent dynamic heuristic extraction for Git repositories and documentation URLs."""
        url_lower = url.lower()
        content_lower = content.lower()
        results: List[Dict[str, str]] = []
        seen = set()

        def add_pkg(name: str, ver: str = "latest", eco: str = "native_c"):
            k = name.lower()
            if k not in seen:
                seen.add(k)
                results.append({"name": name, "version": ver, "ecosystem": eco})

        # 1. Generic Git repository extraction: e.g. https://github.com/owner/repo
        git_match = re.search(r"(?:github\.com|gitlab\.com|bitbucket\.org)/[^/]+/([^/\s?#]+)", url)
        if git_match:
            repo_name = git_match.group(1).replace(".git", "").lower()
            add_pkg(repo_name, "latest", "native_c")

        # 2. Domain-based component extraction for docs sites: e.g. https://domain.org -> domain
        domain_match = re.search(r"https?://(?:www\.)?([^/\.]+)", url)
        if domain_match:
            domain_name = domain_match.group(1).lower()
            if domain_name not in ("github", "gitlab", "bitbucket", "docs", "readthedocs", "pypi", "npmjs", "crates"):
                add_pkg(domain_name, "latest", "native_c")

        # 3. Dynamic scan of content for known package tokens in indexed database
        try:
            from .package_lookup import get_lookup_manager
            known_tokens = get_lookup_manager().get_known_tokens()
        except Exception:
            known_tokens = []

        for token, eco in known_tokens:
            if re.search(rf"\b{re.escape(token)}\b", content_lower):
                ver_match = re.search(rf"{re.escape(token)}[:\s/v=]+([0-9]+\.[0-9]+(\.[0-9]+)?)", content_lower)
                ver = ver_match.group(1) if ver_match else "latest"
                add_pkg(token, ver, eco)

        # 4. Check if primary package has indexed build dependencies in lookup manager
        if results:
            primary_name = results[0]["name"]
            try:
                from .package_lookup import get_lookup_manager
                pkg_info = get_lookup_manager().get(primary_name)
                if pkg_info and "build_deps" in pkg_info:
                    for bd in pkg_info["build_deps"]:
                        if isinstance(bd, dict) and "name" in bd:
                            add_pkg(bd["name"], bd.get("version", "latest"), bd.get("ecosystem", "native_c"))
            except Exception:
                pass

        return results
