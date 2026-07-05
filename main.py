import dotenv
import os
import argparse
import sys
from flow import create_tutorial_flow
from utils.mirror_output import mirror_tutorial_output
from utils.orchestrate import run_orchestration, show_workflow_reminder
from utils.preflight import run_preflight
from utils.profile_presets import load_profile_registry
from utils.project_config import load_project_config, manifest_path, resolve_repo_root

dotenv.load_dotenv(override=True)

DEFAULT_INCLUDE_PATTERNS = {
    "*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.go", "*.java", "*.pyi", "*.pyx",
    "*.c", "*.cc", "*.cpp", "*.h", "*.md", "*.rst", "*Dockerfile",
    "*Makefile", "*.yaml", "*.yml",
}

DEFAULT_EXCLUDE_PATTERNS = {
    "assets/*", "data/*", "images/*", "public/*", "static/*", "temp/*",
    "*docs/*",
    "*venv/*",
    "*.venv/*",
    "*test*",
    "*tests/*",
    "*examples/*",
    "v1/*",
    "*dist/*",
    "*build/*",
    "*experimental/*",
    "*deprecated/*",
    "*misc/*",
    "*legacy/*",
    ".git/*", ".github/*", ".next/*", ".vscode/*",
    "*obj/*",
    "*bin/*",
    "*node_modules/*",
    "*.log"
}


def resolve_mirror_base(args, profile_preset) -> str | None:
    if args.no_mirror:
        return None
    if args.mirror_output:
        return args.mirror_output
    if profile_preset and profile_preset.get("mirror_output_dir"):
        return profile_preset["mirror_output_dir"]
    env_mirror = os.getenv("MIRROR_OUTPUT_DIR", "").strip()
    return env_mirror or None


def run_tutorial(args, profile_preset, profile_name: str | None) -> int:
    if profile_preset and not args.dir and not args.repo:
        args.dir = profile_preset["local_dir"]
    if profile_preset and not args.name:
        args.name = profile_preset["project_name"]
    if profile_preset and args.output == "output":
        args.output = profile_preset["output_dir"]

    mirror_base = resolve_mirror_base(args, profile_preset)

    if args.include:
        include_patterns = set(args.include)
    elif profile_preset:
        include_patterns = profile_preset["include_patterns"]
    else:
        include_patterns = DEFAULT_INCLUDE_PATTERNS

    if args.exclude is not None:
        exclude_patterns = set(args.exclude)
    elif profile_preset:
        exclude_patterns = profile_preset["exclude_patterns"]
    else:
        exclude_patterns = DEFAULT_EXCLUDE_PATTERNS

    if args.max_abstractions is not None:
        max_abstractions = args.max_abstractions
    elif profile_preset:
        max_abstractions = profile_preset["max_abstractions"]
    else:
        max_abstractions = 10

    github_token = None
    if args.repo:
        github_token = args.token or os.environ.get("GITHUB_TOKEN")
        if not github_token:
            print("Warning: No GitHub token provided. You might hit rate limits for public repositories.")

    shared = {
        "repo_url": args.repo,
        "local_dir": args.dir,
        "project_name": args.name,
        "github_token": github_token,
        "output_dir": args.output,
        "include_patterns": include_patterns,
        "exclude_patterns": exclude_patterns,
        "max_file_size": args.max_size,
        "language": args.language,
        "use_cache": not args.no_cache,
        "max_abstraction_num": max_abstractions,
        "files": [],
        "abstractions": [],
        "relationships": {},
        "chapter_order": [],
        "chapters": [],
        "final_output_dir": None,
    }

    print(f"Starting tutorial generation for: {args.repo or args.dir} in {args.language.capitalize()} language")
    print(f"Primary output base: {args.output}")
    print(f"LLM caching: {'Disabled' if args.no_cache else 'Enabled'}")
    if mirror_base:
        print(f"Mirror enabled: {mirror_base} (draft copy after generation)")
    elif profile_preset and profile_preset.get("mirror_output_dir") and args.no_mirror:
        print("Mirror disabled by --no-mirror")

    tutorial_flow = create_tutorial_flow()
    tutorial_flow.run(shared)

    final_dir = shared.get("final_output_dir")
    project_name = shared.get("project_name")
    if mirror_base and final_dir and project_name:
        mirror_tutorial_output(
            final_dir,
            mirror_base,
            project_name,
            profile=profile_name,
            input_dir=args.dir,
        )
    elif mirror_base and not final_dir:
        print("[mirror] Skipped: tutorial output path missing after generation.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Generate a tutorial for a GitHub codebase or local directory.")

    source_group = parser.add_mutually_exclusive_group(required=False)
    source_group.add_argument("--repo", help="URL of the public GitHub repository.")
    source_group.add_argument("--dir", help="Path to local directory.")
    parser.add_argument(
        "--project-config",
        help="Path to .pocketflow/project.json (or set POCKETFLOW_PROJECT_CONFIG).",
    )
    parser.add_argument(
        "--profile",
        help="Named profile from project config pocketflowProfiles.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run manual preflight only (requires --project-config). Exit 0 if ready.",
    )
    parser.add_argument(
        "--orchestrate",
        action="store_true",
        help="Preflight then run all runProfiles from project config.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip staleness block after manual review.",
    )
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip preflight before a single --profile run (orchestrator sets this internally).",
    )
    parser.add_argument(
        "--scaffold-only",
        action="store_true",
        help="Create stub files for missing required preflight docs, then exit.",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        help="Subset of profile names for --orchestrate.",
    )

    parser.add_argument("-n", "--name", help="Project name (optional, derived from repo/directory if omitted).")
    parser.add_argument("-t", "--token", help="GitHub personal access token (optional, reads from GITHUB_TOKEN env var if not provided).")
    parser.add_argument("-o", "--output", default="output", help="Base directory for output (default: ./output).")
    parser.add_argument(
        "--mirror-output",
        help="Optional: copy finished tutorial to {path}/{project_name}/ (does not change primary output).",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="Disable profile/env mirror even when mirror_output_dir is configured.",
    )
    parser.add_argument("-i", "--include", nargs="+", help="Include file patterns (e.g. '*.py' '*.js'). Defaults to common code files if not specified.")
    parser.add_argument("-e", "--exclude", nargs="+", help="Exclude file patterns (e.g. 'tests/*' 'docs/*'). Defaults to test/build directories if not specified.")
    parser.add_argument("-s", "--max-size", type=int, default=100000, help="Maximum file size in bytes (default: 100000, about 100KB).")
    parser.add_argument("--language", default="english", help="Language for the generated tutorial (default: english)")
    parser.add_argument("--no-cache", action="store_true", help="Disable LLM response caching (default: caching enabled)")
    parser.add_argument("--max-abstractions", type=int, default=None, help="Maximum number of abstractions to identify (default: 10, or profile preset)")

    args = parser.parse_args()
    config_path = args.project_config or os.getenv("POCKETFLOW_PROJECT_CONFIG", "").strip() or None
    project_cfg = load_project_config(config_path)

    if args.check_only or args.orchestrate or args.scaffold_only:
        if not project_cfg:
            parser.error("--project-config (or POCKETFLOW_PROJECT_CONFIG) is required for orchestration flags.")
        repo_root = resolve_repo_root(project_cfg)
        os.environ[project_cfg.get("repoRootEnv", "POCKETFLOW_REPO_ROOT")] = repo_root
        os.environ["POCKETFLOW_PROJECT_CONFIG"] = project_cfg["_config_path"]
        return run_orchestration(
            project_cfg,
            check_only=args.check_only,
            force=args.force,
            scaffold_only=args.scaffold_only,
            profiles=args.profiles,
            pocketflow_main=os.path.abspath(__file__),
            python_exe=sys.executable,
        )

    profile_registry = load_profile_registry(config_path)
    if args.profile and args.profile not in profile_registry:
        if profile_registry:
            parser.error(
                f"Unknown profile {args.profile!r}. Available: {', '.join(sorted(profile_registry))}"
            )
        parser.error("--profile requires --project-config with pocketflowProfiles.")

    if not args.repo and not args.dir and not args.profile:
        parser.error("One of --repo, --dir, or --profile is required")

    profile_preset = profile_registry.get(args.profile) if args.profile else None

    if project_cfg and args.profile and not args.no_preflight:
        repo_root = resolve_repo_root(project_cfg)
        os.environ[project_cfg.get("repoRootEnv", "POCKETFLOW_REPO_ROOT")] = repo_root
        project_cfg["_manifest_path"] = manifest_path(project_cfg, repo_root)
        show_workflow_reminder(project_cfg)
        result = run_preflight(
            project_cfg,
            repo_root,
            run_profiles=[args.profile],
            force=args.force,
        )
        from utils.orchestrate import print_preflight_report

        print_preflight_report(project_cfg, result)
        if result.blocked:
            if result.missing_any:
                print("[blocked] Missing required docs.")
            if result.status == "STALE" and not args.force:
                print("[blocked] Docs stale. Use --force after review.")
            if result.status == "CODE_INPUT_LOW":
                print("[blocked] Code source file count below minimum.")
            return 1

    return run_tutorial(args, profile_preset, args.profile)


if __name__ == "__main__":
    raise SystemExit(main())
