import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from .models import AvailabilityStatus

logger = logging.getLogger("package_lookup")

def resolve_lookup_path(custom_path: Optional[Path] = None) -> Path:
    """Resolves the package lookup JSON path from explicit argument, env var, or default location."""
    if custom_path:
        return Path(custom_path)
    env_path = (
        os.environ.get("PACKAGE_LOOKUP_PATH")
        or os.environ.get("PACKAGE_LOOKUP_FILE")
        or os.environ.get("PACKAGES_LOOKUP_PATH")
    )
    if env_path and env_path.strip():
        return Path(env_path.strip())
    return Path(__file__).parent / "data" / "packages_lookup.json"


_DEFAULT_LOOKUP_PATH = resolve_lookup_path()


def normalize_status(val: Any) -> AvailabilityStatus:
    """Safely convert a string, enum, or name into AvailabilityStatus."""
    if isinstance(val, AvailabilityStatus):
        return val
    s = str(val or "").strip().lower()
    for status in AvailabilityStatus:
        if status.value.lower() == s or status.name.lower() == s:
            return status
    return AvailabilityStatus.UNPORTED_BUILD_REQUIRED


class PackageLookupManager:
    """Manages dynamic, file-backed package lookup data.
    
    Prevents hardcoding package data in code. Reuses previous analyses
    and refreshes entries when a new version analysis is requested,
    drastically reducing calls to LLMs and remote registries.
    
    Supports mounted persistent volumes and auto-reloads when the underlying
    file is updated on the host or inside a container.
    """

    def __init__(self, filepath: Optional[Path] = None):
        self.filepath = resolve_lookup_path(filepath)
        self._lock = threading.RLock()
        self._last_mtime: float = 0.0
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load(force=True)

    def _load(self, force: bool = False):
        """Loads package lookup data from the JSON file if modified or forced."""
        with self._lock:
            if self.filepath.exists():
                try:
                    current_mtime = self.filepath.stat().st_mtime
                    if not force and current_mtime <= self._last_mtime and self._data:
                        return
                    content = self.filepath.read_text(encoding="utf-8")
                    self._data = json.loads(content)
                    self._last_mtime = current_mtime
                    logger.info("Loaded %d packages from mounted lookup at %s (mtime=%.2f)", len(self._data), self.filepath, self._last_mtime)
                except Exception as exc:
                    logger.warning("Could not read package lookup file %s: %s", self.filepath, exc)
                    if not self._data:
                        self._data = {}
            else:
                self._data = {}

    def _save(self):
        """Atomically saves the package lookup data to disk."""
        with self._lock:
            try:
                self.filepath.parent.mkdir(parents=True, exist_ok=True)
                dir_path = self.filepath.parent
                with tempfile.NamedTemporaryFile("w", dir=dir_path, delete=False, encoding="utf-8") as tf:
                    json.dump(self._data, tf, indent=2, ensure_ascii=False)
                    temp_name = tf.name
                os.replace(temp_name, self.filepath)
                if self.filepath.exists():
                    self._last_mtime = self.filepath.stat().st_mtime
                logger.info("Persisted %d packages to mounted lookup at %s", len(self._data), self.filepath)
            except Exception as exc:
                logger.error("Failed to save package lookup file %s: %s", self.filepath, exc)

    def get(self, package_name: str, requested_version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Look up a package by name and optional requested version.
        
        If requested_version is specified (e.g. '1.25') and does not match the
        cached version or versions map, returns None so that a fresh analysis
        for the new version is performed and saved.
        """
        if not package_name:
            return None
        self._load()
        key = package_name.strip().lower()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None

            entry_copy = dict(entry)
            req_ver = (requested_version or "").strip().lstrip("v").lower()

            # If no specific version requested, return latest cached analysis
            if not req_ver or req_ver in ("latest", "master", "main", "*"):
                entry_copy["status"] = normalize_status(entry_copy.get("status"))
                entry_copy["cached_hit"] = True
                return entry_copy

            # Check if this exact requested version exists in version history
            versions_map = entry.get("versions", {})
            for v_key, v_data in versions_map.items():
                if v_key.strip().lstrip("v").lower() == req_ver:
                    merged = dict(entry_copy)
                    merged.update(v_data)
                    merged["status"] = normalize_status(merged.get("status"))
                    merged["cached_hit"] = True
                    return merged

            # Check if primary entry version matches
            entry_ver = str(entry.get("version", "")).strip().lstrip("v").lower()
            avail_ver = str(entry.get("available_version", "")).strip().lstrip("v").lower()
            if req_ver in (entry_ver, avail_ver):
                entry_copy["status"] = normalize_status(entry_copy.get("status"))
                entry_copy["cached_hit"] = True
                return entry_copy

            # Different / new version requested! Return None so new version is analyzed
            return None

    def save_or_refresh(
        self,
        package_name: str,
        version: str = "latest",
        probe_result: Optional[Dict[str, Any]] = None,
        arch_posture: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Save or refresh an analyzed package entry in the lookup file."""
        if not package_name:
            return {}

        key = package_name.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            existing = self._data.get(key, {})
            versions_map = existing.get("versions", {})

            ver_clean = str(version or "latest").strip().lstrip("v")
            version_entry = {}
            if probe_result:
                stat = probe_result.get("status", "NATIVE_AVAILABLE")
                if isinstance(stat, AvailabilityStatus):
                    stat = stat.value

                version_entry = {
                    "status": str(stat),
                    "available_version": probe_result.get("available_version") or ver_clean,
                    "tier": probe_result.get("tier", ""),
                    "evidence": probe_result.get("evidence", ""),
                    "url": probe_result.get("url", ""),
                    "substitute": probe_result.get("substitute"),
                    "version_warning": probe_result.get("version_warning"),
                    "last_analyzed": now_iso,
                }
                versions_map[ver_clean] = version_entry

            # Merge primary record
            record = dict(existing)
            record["package_name"] = key
            record["version"] = ver_clean if ver_clean != "latest" else record.get("version", "latest")
            record["last_analyzed"] = now_iso
            record["analysis_count"] = record.get("analysis_count", 0) + 1
            record["versions"] = versions_map

            if probe_result:
                stat = probe_result.get("status", record.get("status", "NATIVE_AVAILABLE"))
                if isinstance(stat, AvailabilityStatus):
                    stat = stat.value
                record["status"] = str(stat)
                record["available_version"] = probe_result.get("available_version") or record.get("available_version") or ver_clean
                record["tier"] = probe_result.get("tier", record.get("tier", ""))
                record["evidence"] = probe_result.get("evidence", record.get("evidence", ""))
                record["url"] = probe_result.get("url", record.get("url", ""))
                if "substitute" in probe_result:
                    record["substitute"] = probe_result["substitute"]

            if arch_posture:
                record["arch_posture"] = arch_posture

            if metadata:
                for k, v in metadata.items():
                    if v:
                        record[k] = v

            self._data[key] = record
            self._save()
            return record

    def get_metadata(self, package_name: str) -> Optional[Dict[str, str]]:
        """Return metadata (git_repo_url, doc_url, ecosystem, version)."""
        if not package_name:
            return None
        self._load()
        key = package_name.strip().lower()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            return {
                "git_repo_url": entry.get("git_repo_url", ""),
                "doc_url": entry.get("doc_url", ""),
                "ecosystem": entry.get("ecosystem", "container"),
                "version": entry.get("version", "latest"),
            }

    def get_arch_posture(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Return recorded architecture posture scan dictionary."""
        if not package_name:
            return None
        self._load()
        key = package_name.strip().lower()
        with self._lock:
            entry = self._data.get(key)
            if entry and "arch_posture" in entry:
                return entry["arch_posture"]
            return None

    def get_known_tokens(self) -> List[Tuple[str, str]]:
        """Return list of (package_name, ecosystem) for URL and text scanners."""
        self._load()
        with self._lock:
            return [
                (pkg, entry.get("ecosystem", "container"))
                for pkg, entry in self._data.items()
            ]

    def all_packages(self) -> Dict[str, Dict[str, Any]]:
        """Return a copy of all known packages with normalized status enums."""
        self._load()
        with self._lock:
            res = {}
            for k, v in self._data.items():
                item = dict(v)
                item["status"] = normalize_status(item.get("status"))
                res[k] = item
            return res

    def get_info(self) -> Dict[str, Any]:
        """Return diagnostic and mounting information about the package lookup file."""
        self._load()
        with self._lock:
            return {
                "filepath": str(self.filepath),
                "is_mounted": self.filepath.exists(),
                "package_count": len(self._data),
                "packages": sorted(list(self._data.keys())),
                "last_modified": (
                    datetime.fromtimestamp(self._last_mtime, timezone.utc).isoformat()
                    if self._last_mtime > 0
                    else None
                ),
            }


_INSTANCE: Optional[PackageLookupManager] = None
_INIT_LOCK = threading.Lock()


def get_lookup_manager() -> PackageLookupManager:
    """Singleton getter for the package lookup manager."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INIT_LOCK:
            if _INSTANCE is None:
                _INSTANCE = PackageLookupManager()
    return _INSTANCE
