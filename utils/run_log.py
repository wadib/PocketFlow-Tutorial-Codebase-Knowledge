"""Optional orchestration run log (path driven by project.json)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


def write_run_log(cfg: dict[str, Any], repo_root: str, run: dict[str, Any]) -> str | None:
    vault_root = cfg.get("hermesVaultRoot") or os.getenv("HERMESVAULT_ROOT", "")
    vault_project = cfg.get("vaultProjectRelative", "").strip()
    if not vault_root or not vault_project:
        return None

    log_rel = cfg.get("vaultRunLogRelative", "Manuals/PocketFlow-Runs")
    runs_dir = os.path.join(vault_root, vault_project, log_rel)
    os.makedirs(runs_dir, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    log_path = os.path.join(runs_dir, f"{stamp} - orchestrated run.md")
    project_name = cfg.get("projectName") or os.path.basename(repo_root)

    lines = [
        "---",
        "type: note",
        "status: active",
        f"created: {datetime.now().strftime('%Y-%m-%d')}",
        f"updated: {datetime.now().strftime('%Y-%m-%dT%H:%M')}",
        f"project: {project_name}",
        "tags:",
        "  - source/pocketflow",
        "  - type/note",
        "---",
        "",
        f"# PocketFlow orchestrated run - {stamp} (UTC)",
        "",
        "## Status",
        "",
        f"- **Result:** {run.get('result')}",
        f"- **Preflight:** {run.get('preflight_status')}",
        f"- **Profiles:** {', '.join(run.get('profiles') or [])}",
        f"- **Force:** {run.get('force')}",
        "",
        "## Manual preflight",
        "",
    ]

    for heading, docs in (("Customer", run.get("customer_docs")), ("Admin", run.get("admin_docs"))):
        if not docs:
            continue
        lines.extend([f"### {heading}", ""])
        for doc in docs:
            flag = "present" if doc.exists else "**MISSING**"
            lines.append(f"- [{flag}] `{doc.file}`")
        lines.append("")

    code_state = run.get("code_state")
    if code_state:
        lines.extend(
            [
                "### Code",
                "",
                f"- Source files: {code_state.source_file_count} (min {code_state.min_required})",
                "",
            ]
        )

    if run.get("stale_reason"):
        lines.extend(["## Stale reason", "", run["stale_reason"], ""])

    profile_results = run.get("profile_results")
    if profile_results:
        lines.extend(["## PocketFlow execution", ""])
        for item in profile_results:
            lines.append(f"- **{item['profile']}:** exit {item['exit_code']} - {item['note']}")
        lines.append("")

    mirror_sub = cfg.get("vaultDraftMirrorSubpath", "Manuals/PocketFlow-Drafts")
    lines.extend(
        [
            "## Draft mirror",
            "",
            f"- Vault subpath: `{mirror_sub}`",
            "- Config: `.pocketflow/project.json`",
            "- Manifest: `.pocketflow/last-run.json`",
            "",
        ]
    )

    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

    return log_path
