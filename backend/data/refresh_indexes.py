#!/usr/bin/env python3
"""
Refresh script for ppc64le availability index files.

Sources refreshed (all via shallow local clone):
  1. ppc64le/pyeco            → devpi_wheels_index.json    (DevPi Python wheels)
  2. ICR-Power-Image-Tracker  → icr_power_images.json      (ICR container catalogue)
  3. ppc64le/build-scripts    → build_scripts_index.json   (packages with build_info.json)

Run manually or via a monthly cron/scheduler:
  python3 gemini-elite-ai/backend/data/refresh_indexes.py

GitHub Actions example (1st of every month at 03:00 UTC):
  - cron: '0 3 1 * *'
"""

import re
import json
import shutil
import subprocess
import sys
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

PYECO_REPO      = "https://github.com/ppc64le/pyeco.git"
ICR_REPO        = "https://github.com/seth-priya/ICR-Power-Image-Tracker.git"
BUILD_SCRIPTS_REPO = "https://github.com/ppc64le/build-scripts.git"

logger = logging.getLogger("refresh_indexes")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shallow_clone(repo_url: str, target_dir: Path) -> None:
    """Shallow-clone *repo_url* into *target_dir* (depth=1, no tags)."""
    logger.info("Cloning %s …", repo_url)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--no-tags", "--quiet", repo_url, str(target_dir)],
        check=True,
        capture_output=True,
    )
    logger.info("  → cloned into %s", target_dir)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 1. DevPi Wheels Index  (ppc64le/pyeco  →  DevpiWheelsIndex.md)
# ---------------------------------------------------------------------------

def _parse_devpi_wheels(md_text: str) -> dict:
    packages: dict = {}
    current_pkg: str | None = None
    current_ver: str | None = None
    last_updated: str | None = None

    for line in md_text.splitlines():
        s = line.strip()

        if "Last Updated On:" in s:
            m = re.search(r"Last Updated On:\s*(.+)", s)
            if m:
                last_updated = m.group(1).strip().strip("*").strip()
            continue

        if s.startswith("### "):
            current_pkg = s[4:].strip()
            packages[current_pkg] = {
                "versions": [],
                "latest_ppc64le_version": None,
                "latest_noarch_version": None,
                "has_ppc64le_wheel": False,
                "has_noarch_wheel": False,
            }
            current_ver = None

        elif s.startswith("- **") and "==" in s and current_pkg:
            m = re.search(r"\*\*(.+?)==(.+?)\*\*", s)
            if m:
                current_ver = m.group(2).strip()

        elif s.startswith("|") and current_pkg and current_ver and ".whl" in s:
            parts = s.split("|")
            if len(parts) >= 2:
                cell = parts[1].strip()
                wheels = [w.strip() for w in cell.replace("<br>", "\n").splitlines() if ".whl" in w]
                has_ppc64le = any("ppc64le" in w for w in wheels)
                has_noarch  = any("none-any" in w for w in wheels)
                clean_ver   = current_ver.split("+")[0]   # strip +ppc64le1 suffix
                pkg = packages[current_pkg]
                if clean_ver not in pkg["versions"]:
                    pkg["versions"].append(clean_ver)
                if has_ppc64le and not pkg["has_ppc64le_wheel"]:
                    pkg["has_ppc64le_wheel"]       = True
                    pkg["latest_ppc64le_version"]  = clean_ver
                if has_noarch and not pkg["has_noarch_wheel"]:
                    pkg["has_noarch_wheel"]        = True
                    pkg["latest_noarch_version"]   = clean_ver

    return {"last_updated_upstream": last_updated, "packages": packages}


def refresh_devpi_wheels(tmpdir: Path) -> None:
    repo_dir = tmpdir / "pyeco"
    _shallow_clone(PYECO_REPO, repo_dir)

    md_file = repo_dir / "DevpiWheelsIndex.md"
    if not md_file.exists():
        raise FileNotFoundError(f"DevpiWheelsIndex.md not found in cloned repo at {md_file}")

    parsed = _parse_devpi_wheels(md_file.read_text(encoding="utf-8"))

    result = {
        "metadata": {
            "source": "https://github.com/ppc64le/pyeco/blob/main/DevpiWheelsIndex.md",
            "last_updated_upstream": parsed["last_updated_upstream"],
            "fetched_at": _now_iso(),
            "total_packages": len(parsed["packages"]),
        },
        "packages": parsed["packages"],
    }

    out_path = SCRIPT_DIR / "devpi_wheels_index.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info("Wrote %s  (%d packages)", out_path, result["metadata"]["total_packages"])


# ---------------------------------------------------------------------------
# 2. ICR Power Image Tracker  (ICR-Power-Image-Tracker  →  docs/index.md)
# ---------------------------------------------------------------------------

def _parse_icr_images(md_text: str) -> list[dict]:
    images: list[dict] = []
    in_table = False

    for line in md_text.splitlines():
        s = line.strip()
        if s.startswith("|") and "Image Name" in s:
            in_table = True
            continue
        if re.match(r"^\|[-: |]+\|$", s):   # separator row
            continue
        if not in_table:
            continue
        if not s.startswith("|"):
            in_table = False
            continue

        parts = [p.strip() for p in s.strip("|").split("|")]
        if len(parts) < 4:
            continue

        raw_name = parts[0].strip("`")
        tag      = parts[1].strip("`")
        pull_cmd = parts[3] if len(parts) > 3 else ""
        m = re.search(r"docker pull\s+(icr\.io/[^\s`]+)", pull_cmd)
        full_ref = m.group(1) if m else f"icr.io/ppc64le-oss/{raw_name}:{tag}"

        # Canonical lookup key: strip trailing -ppc64le for fuzzy matching
        canonical = re.sub(r"-ppc64le$", "", raw_name).lower()

        images.append({
            "image_name":    raw_name,
            "canonical_name": canonical,
            "tag":           tag,
            "full_ref":      full_ref,
            "license":       parts[2] if len(parts) > 2 else "",
            "last_published": parts[4].strip() if len(parts) > 4 else "",
        })

    return images


def refresh_icr_images(tmpdir: Path) -> None:
    repo_dir = tmpdir / "icr-tracker"
    _shallow_clone(ICR_REPO, repo_dir)

    md_file = repo_dir / "docs" / "index.md"
    if not md_file.exists():
        raise FileNotFoundError(f"docs/index.md not found in cloned repo at {md_file}")

    images = _parse_icr_images(md_file.read_text(encoding="utf-8"))

    # Build lookup: canonical_name → list of entries
    lookup: dict[str, list[dict]] = {}
    for img in images:
        lookup.setdefault(img["canonical_name"], []).append(img)

    result = {
        "metadata": {
            "source": "https://github.com/seth-priya/ICR-Power-Image-Tracker/blob/main/docs/index.md",
            "fetched_at": _now_iso(),
            "total_entries": len(images),
            "total_images":  len(lookup),
        },
        "lookup":  lookup,
        "entries": images,
    }

    out_path = SCRIPT_DIR / "icr_power_images.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info("Wrote %s  (%d unique images, %d entries)", out_path, len(lookup), len(images))


# ---------------------------------------------------------------------------
# 3. ppc64le/build-scripts  (find all build_info.json files locally)
# ---------------------------------------------------------------------------

def refresh_build_scripts(tmpdir: Path) -> None:
    repo_dir = tmpdir / "build-scripts"
    _shallow_clone(BUILD_SCRIPTS_REPO, repo_dir)

    all_packages: list[dict] = []

    for info_file in sorted(repo_dir.rglob("build_info.json")):
        try:
            info = json.loads(info_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug("Skipping malformed %s: %s", info_file, exc)
            continue

        # Relative path from repo root, e.g. "r/rocksdb"
        pkg_dir = info_file.parent.relative_to(repo_dir)

        all_packages.append({
            "package_name":     info.get("package_name", info_file.parent.name),
            "version":          info.get("version", ""),
            "github_url":       info.get("github_url", ""),
            "package_dir":      str(pkg_dir),
            "build_script":     info.get("build_script", ""),
            "wheel_build":      bool(info.get("wheel_build", False)),
            "raw_build_info_url": (
                f"https://raw.githubusercontent.com/ppc64le/build-scripts/master/{pkg_dir}/build_info.json"
            ),
        })

    logger.info("Found %d packages with build_info.json", len(all_packages))

    # Lookup dict: lower-case package name → entry
    lookup: dict[str, dict] = {}
    for pkg in all_packages:
        key = pkg["package_name"].lower()
        # Keep the most recently encountered entry (last in sorted order)
        lookup[key] = pkg

    result = {
        "metadata": {
            "source": "https://github.com/ppc64le/build-scripts",
            "note":   "Only packages containing a build_info.json file are included",
            "fetched_at":     _now_iso(),
            "total_packages": len(all_packages),
        },
        "lookup":   lookup,
        "packages": all_packages,
    }

    out_path = SCRIPT_DIR / "build_scripts_index.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info("Wrote %s  (%d packages)", out_path, len(all_packages))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ppc64le_refresh_") as tmp:
        tmpdir = Path(tmp)
        errors: list[str] = []

        for fn, name in [
            (refresh_devpi_wheels,  "DevPi Wheels Index"),
            (refresh_icr_images,    "ICR Power Image Tracker"),
            (refresh_build_scripts, "ppc64le/build-scripts index"),
        ]:
            try:
                fn(tmpdir)
            except Exception as exc:
                logger.error("Failed to refresh %s: %s", name, exc)
                errors.append(name)

    if errors:
        logger.error("Refresh completed with errors in: %s", ", ".join(errors))
        sys.exit(1)
    else:
        logger.info("All indexes refreshed successfully.")


if __name__ == "__main__":
    main()
