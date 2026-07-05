"""Load per-project PocketFlow settings from .pocketflow/project.json."""

from __future__ import annotations

import json
import os
from typing import Any


def resolve_config_path(explicit: str | None = None) -> str | None:
    path = (explicit or os.getenv("POCKETFLOW_PROJECT_CONFIG", "")).strip()
    return path if path and os.path.isfile(path) else None


def load_project_config(config_path: str | None = None) -> dict[str, Any] | None:
    path = resolve_config_path(config_path)
    if not path:
        return None
    with open(path, encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["_config_path"] = os.path.abspath(path)
    return cfg


def resolve_repo_root(cfg: dict[str, Any]) -> str:
    repo_env = cfg.get("repoRootEnv", "POCKETFLOW_REPO_ROOT")
    repo_root = os.getenv(repo_env, "").strip() or cfg.get("repoRoot", "").strip()
    if not repo_root:
        config_dir = os.path.dirname(cfg["_config_path"])
        repo_root = os.path.dirname(config_dir)
    return os.path.abspath(repo_root)


def _as_pattern_set(values) -> set[str]:
    if not values:
        return set()
    if isinstance(values, (list, tuple, set)):
        return set(values)
    return {values}


def load_profiles_from_config(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    repo_root = resolve_repo_root(cfg)
    hermes_root = os.getenv("HERMESVAULT_ROOT", cfg.get("hermesVaultRoot", "")).strip()
    vault_project = cfg.get("vaultProjectRelative", "").strip()
    mirror_subpath = cfg.get("vaultDraftMirrorSubpath", "Manuals/PocketFlow-Drafts")

    profiles: dict[str, dict[str, Any]] = {}
    for name, preset in cfg.get("pocketflowProfiles", {}).items():
        local_dir = preset.get("localDir") or preset.get("local_dir", ".")
        if not os.path.isabs(local_dir):
            local_dir = os.path.join(repo_root, local_dir)

        mirror_output_dir = preset.get("mirror_output_dir") or preset.get("mirrorOutputDir")
        if not mirror_output_dir and hermes_root and vault_project:
            mirror_output_dir = os.path.join(hermes_root, vault_project, mirror_subpath)

        profiles[name] = {
            "local_dir": os.path.abspath(local_dir),
            "include_patterns": _as_pattern_set(
                preset.get("includePatterns") or preset.get("include_patterns")
            ),
            "exclude_patterns": _as_pattern_set(
                preset.get("excludePatterns") or preset.get("exclude_patterns")
            ),
            "project_name": preset.get("projectName") or preset.get("project_name", name),
            "output_dir": preset.get("outputDir") or preset.get("output_dir", f"./output/{name}"),
            "mirror_output_dir": mirror_output_dir,
            "max_abstractions": int(
                preset.get("maxAbstractions") or preset.get("max_abstractions") or 10
            ),
        }
    return profiles


def manifest_path(cfg: dict[str, Any], repo_root: str) -> str:
    rel = cfg.get("lastRunManifest", ".pocketflow/last-run.json")
    return os.path.join(repo_root, rel)
