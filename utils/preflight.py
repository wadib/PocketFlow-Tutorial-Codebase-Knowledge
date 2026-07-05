"""Generic manual/source preflight from project.json."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocState:
    file: str
    path: str
    exists: bool
    sha256: str | None = None


@dataclass
class CodeState:
    source_file_count: int
    min_required: int
    ok: bool
    label: str = "code"


@dataclass
class PreflightResult:
    status: str  # READY | MISSING | STALE | CODE_INPUT_LOW
    blocked: bool
    customer_docs: list[DocState] = field(default_factory=list)
    admin_docs: list[DocState] = field(default_factory=list)
    code_state: CodeState | None = None
    fingerprint: str = ""
    stale_reason: str | None = None
    missing_any: bool = False


def _preflight_section(cfg: dict[str, Any], name: str) -> dict[str, Any] | None:
    preflight = cfg.get("preflight") or {}
    section = preflight.get(name)
    if section:
        return section
    return cfg.get(name)


def _file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _required_doc_state(repo_root: str, section: dict[str, Any]) -> list[DocState]:
    base = os.path.join(repo_root, section["directory"])
    results: list[DocState] = []
    for name in section.get("requiredFiles", []):
        full = os.path.join(base, name)
        exists = os.path.isfile(full)
        results.append(
            DocState(
                file=name,
                path=full,
                exists=exists,
                sha256=_file_sha256(full) if exists else None,
            )
        )
    return results


def _count_source_files(repo_root: str, section: dict[str, Any]) -> int:
    patterns = section.get("includePatterns") or section.get("include_patterns") or ["*.cs"]
    excludes = section.get("excludePatterns") or section.get("exclude_patterns") or [
        "bin/*",
        "obj/*",
        "*Migrations*",
    ]
    count = 0
    for root, _, files in os.walk(repo_root):
        rel_root = os.path.relpath(root, repo_root)
        if rel_root == ".":
            rel_root = ""
        for name in files:
            rel = name if not rel_root else os.path.join(rel_root, name)
            rel_norm = rel.replace("\\", "/")
            if any(fnmatch.fnmatch(rel_norm, ex.replace("\\", "/")) for ex in excludes):
                continue
            if any(fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel_norm, pat) for pat in patterns):
                count += 1
    return count


def _code_state(repo_root: str, section: dict[str, Any]) -> CodeState:
    minimum = section.get("minSourceFileCount")
    if minimum is None:
        minimum = section.get("minCsFileCount", 0)
    minimum = int(minimum)
    count = _count_source_files(repo_root, section)
    return CodeState(
        source_file_count=count,
        min_required=minimum,
        ok=count >= minimum,
        label=section.get("label", "code"),
    )


def input_fingerprint(*doc_groups: list[DocState]) -> str:
    parts: list[str] = []
    for group in doc_groups:
        for doc in group:
            if doc.exists and doc.sha256:
                parts.append(f"{doc.file}={doc.sha256}")
    return "|".join(parts)


def run_preflight(
    cfg: dict[str, Any],
    repo_root: str,
    *,
    run_profiles: list[str] | None = None,
    force: bool = False,
    check_only: bool = False,
) -> PreflightResult:
    customer_section = _preflight_section(cfg, "customer")
    admin_section = _preflight_section(cfg, "admin")
    code_section = _preflight_section(cfg, "code")

    customer_docs = _required_doc_state(repo_root, customer_section) if customer_section else []
    admin_docs = _required_doc_state(repo_root, admin_section) if admin_section else []
    code_state = _code_state(repo_root, code_section) if code_section else None

    missing_any = any(not d.exists for d in customer_docs + admin_docs)
    fingerprint = input_fingerprint(customer_docs, admin_docs)

    profiles = run_profiles or cfg.get("runProfiles") or []
    status = "READY"
    stale_reason = None

    if missing_any:
        status = "MISSING"
    elif code_state and not code_state.ok and "code" in profiles:
        status = "CODE_INPUT_LOW"
    else:
        manifest = cfg.get("_manifest_path")
        if manifest and os.path.isfile(manifest):
            with open(manifest, encoding="utf-8") as handle:
                last = json.load(handle)
            if last.get("inputFingerprint") and last["inputFingerprint"] != fingerprint:
                status = "STALE"
                stale_reason = (
                    "Curated docs changed since last successful run. "
                    "Review, then re-run or use --force."
                )

    blocked = missing_any or (status == "STALE" and not force)
    if code_state and not code_state.ok and "code" in profiles and not check_only:
        blocked = blocked or status == "CODE_INPUT_LOW"

    return PreflightResult(
        status=status,
        blocked=blocked,
        customer_docs=customer_docs,
        admin_docs=admin_docs,
        code_state=code_state,
        fingerprint=fingerprint,
        stale_reason=stale_reason,
        missing_any=missing_any,
    )


def scaffold_missing(repo_root: str, cfg: dict[str, Any]) -> list[str]:
    created: list[str] = []
    for section in (_preflight_section(cfg, "customer"), _preflight_section(cfg, "admin")):
        if not section:
            continue
        base = os.path.join(repo_root, section["directory"])
        os.makedirs(base, exist_ok=True)
        for name in section.get("requiredFiles", []):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                continue
            title = os.path.splitext(name)[0]
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(f"# {title}\n\n> Scaffold stub - replace with curated content before PocketFlow.\n\n")
            created.append(path)
    return created
