"""Optional post-run mirror of generated tutorial folders.

Keeps PocketFlow's default output layout under ./output/ unchanged.
Mirrors only when explicitly requested (CLI, profile preset, or env).
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _normalize(path: str) -> str:
    return os.path.normpath(os.path.abspath(path))


def resolve_mirror_destination(mirror_base: str, project_name: str) -> str:
    """Return {mirror_base}/{project_name}/ — same subfolder layout as default output."""
    if not mirror_base:
        raise ValueError("mirror_base is required")
    if not project_name:
        raise ValueError("project_name is required for mirror destination")
    return _normalize(os.path.join(mirror_base, project_name))


def _validate_mirror_paths(source_dir: str, dest_dir: str) -> None:
    source = _normalize(source_dir)
    dest = _normalize(dest_dir)

    if not os.path.isdir(source):
        raise FileNotFoundError(f"Mirror source does not exist: {source}")

    if source == dest:
        raise ValueError("Mirror destination must differ from source")

    # Prevent copying a parent into its child or vice versa.
    source_parts = Path(source).parts
    dest_parts = Path(dest).parts
    if len(source_parts) <= len(dest_parts) and dest_parts[: len(source_parts)] == source_parts:
        raise ValueError(f"Mirror destination is inside source: {dest}")
    if len(dest_parts) <= len(source_parts) and source_parts[: len(dest_parts)] == dest_parts:
        raise ValueError(f"Mirror source is inside destination: {dest}")


def mirror_tutorial_output(
    source_dir: str,
    mirror_base: str,
    project_name: str,
    *,
    profile: str | None = None,
    input_dir: str | None = None,
) -> str:
    """Copy tutorial output to mirror_base/project_name. Returns destination path."""
    dest_dir = resolve_mirror_destination(mirror_base, project_name)
    source = _normalize(source_dir)
    _validate_mirror_paths(source, dest_dir)

    os.makedirs(dest_dir, exist_ok=True)

    print("[mirror] PocketFlow tutorial mirror (draft copy — does not replace curated manuals)")
    print(f"[mirror]   source:  {source}")
    print(f"[mirror]   mirror:  {dest_dir}")
    if profile:
        print(f"[mirror]   profile: {profile}")

    copied_files = 0
    for root, _, files in os.walk(source):
        rel = os.path.relpath(root, source)
        target_root = dest_dir if rel == "." else os.path.join(dest_dir, rel)
        os.makedirs(target_root, exist_ok=True)
        for name in files:
            shutil.copy2(os.path.join(root, name), os.path.join(target_root, name))
            copied_files += 1

    log_path = os.path.join(dest_dir, "_pocketflow_mirror_log.json")
    log_entry = {
        "mirrored_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": source,
        "mirror_base": _normalize(mirror_base),
        "destination_dir": dest_dir,
        "project_name": project_name,
        "profile": profile,
        "input_dir": _normalize(input_dir) if input_dir else None,
        "file_count": copied_files,
        "note": "AI-generated draft. Not the curated manual source of truth.",
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2)
        f.write("\n")

    print(f"[mirror]   files:   {copied_files}")
    print(f"[mirror]   log:     {log_path}")
    print("[mirror] Done.")
    return dest_dir
