"""Orchestration: preflight, multi-profile runs, manifest, optional run log."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from utils.preflight import PreflightResult, run_preflight, scaffold_missing
from utils.project_config import load_profiles_from_config, manifest_path, resolve_repo_root
from utils.run_log import write_run_log


def _print_step(number: int, text: str) -> None:
    print(f"  {number}. {text}")


def show_workflow_reminder(cfg: dict[str, Any]) -> None:
    steps = cfg.get("workflowSteps") or []
    if not steps:
        return
    print("")
    print("=== PocketFlow workflow (manuals first) ===")
    for index, step in enumerate(steps, start=1):
        _print_step(index, step)
    print("")


def _print_doc(label: str, directory: str, docs) -> None:
    if not docs:
        return
    print(f"{label} ({directory}):")
    for doc in docs:
        if doc.exists:
            print(f"[ok] {doc.file}")
        else:
            print(f"[blocked] MISSING: {doc.file}")


def print_preflight_report(
    cfg: dict[str, Any],
    result: PreflightResult,
    *,
    customer_dir: str | None = None,
    admin_dir: str | None = None,
) -> None:
    print("=== Manual preflight ===")
    customer_section = (cfg.get("preflight") or {}).get("customer")
    admin_section = (cfg.get("preflight") or {}).get("admin")
    if result.customer_docs:
        _print_doc(
            "Customer",
            customer_dir or (customer_section or {}).get("directory", ""),
            result.customer_docs,
        )
    if result.admin_docs:
        _print_doc(
            "Admin",
            admin_dir or (admin_section or {}).get("directory", ""),
            result.admin_docs,
        )
    if result.code_state:
        if result.code_state.ok:
            print(f"[ok] Code: {result.code_state.source_file_count} source files")
        else:
            print(
                f"[blocked] Code: {result.code_state.source_file_count} source files "
                f"(need {result.code_state.min_required})"
            )
    if result.stale_reason:
        print(f"[warn] {result.stale_reason}")
    elif result.status == "READY" and not os.path.isfile(cfg.get("_manifest_path", "")):
        print("[warn] No .pocketflow/last-run.json yet. Review manuals before first PocketFlow run.")


from datetime import datetime, timezone


def save_manifest(path: str, fingerprint: str, profiles: list[str], log_path: str | None) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "lastSuccessUtc": datetime.now(timezone.utc).isoformat(),
        "inputFingerprint": fingerprint,
        "profiles": profiles,
        "hermesRunLog": log_path,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def run_orchestration(
    cfg: dict[str, Any],
    *,
    check_only: bool = False,
    force: bool = False,
    scaffold_only: bool = False,
    profiles: list[str] | None = None,
    pocketflow_main: str,
    python_exe: str | None = None,
) -> int:
    repo_root = resolve_repo_root(cfg)
    os.environ[cfg.get("repoRootEnv", "POCKETFLOW_REPO_ROOT")] = repo_root
    cfg["_manifest_path"] = manifest_path(cfg, repo_root)

    run_profiles = profiles or list(cfg.get("runProfiles") or [])
    show_workflow_reminder(cfg)

    if scaffold_only:
        created = scaffold_missing(repo_root, cfg)
        if not created:
            print("[ok] Nothing to scaffold.")
            return 0
        print(f"[warn] Scaffolded {len(created)} stub(s). Edit before PocketFlow.")
        return 0

    result = run_preflight(
        cfg,
        repo_root,
        run_profiles=run_profiles,
        force=force,
        check_only=check_only,
    )
    print_preflight_report(cfg, result)

    if check_only:
        if result.blocked or result.status != "READY":
            print(f"Preflight: {result.status} - NOT ready.")
            return 1
        print(f"Preflight: {result.status} - ready for PocketFlow.")
        return 0

    run_payload = {
        "result": "BLOCKED",
        "preflight_status": result.status,
        "profiles": run_profiles,
        "force": force,
        "customer_docs": result.customer_docs,
        "admin_docs": result.admin_docs,
        "code_state": result.code_state,
        "stale_reason": result.stale_reason,
        "profile_results": None,
    }

    if result.blocked:
        if result.missing_any:
            print("[blocked] Missing required docs. Edit or use --scaffold-only.")
        if result.status == "STALE" and not force:
            print("[blocked] Docs stale. Use --check-only then --force after review.")
        if result.status == "CODE_INPUT_LOW":
            print("[blocked] Code source file count below minimum.")
        log_path = write_run_log(cfg, repo_root, run_payload)
        if log_path:
            print(f"[warn] Run log: {log_path}")
        return 1

    python = python_exe or sys.executable
    config_path = cfg["_config_path"]
    profile_results: list[dict[str, Any]] = []
    all_ok = True

    print("=== Running PocketFlow ===")
    for profile in run_profiles:
        print(f"--- {profile} ---")
        cmd = [
            python,
            pocketflow_main,
            "--project-config",
            config_path,
            "--profile",
            profile,
            "--no-preflight",
        ]
        completed = subprocess.run(cmd, check=False)
        exit_code = completed.returncode
        note = "ok" if exit_code == 0 else "failed"
        profile_results.append({"profile": profile, "exit_code": exit_code, "note": note})
        if exit_code != 0:
            all_ok = False

    run_payload["profile_results"] = profile_results
    run_payload["result"] = "SUCCESS" if all_ok else "PARTIAL_FAILURE"
    log_path = write_run_log(cfg, repo_root, run_payload)

    if all_ok:
        save_manifest(cfg["_manifest_path"], result.fingerprint, run_profiles, log_path)
        print(f"[ok] Done. Log: {log_path}")
        return 0

    print(f"[blocked] Profile failure. Log: {log_path}")
    return 1
