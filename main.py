import dotenv
import os
import argparse
from flow import create_tutorial_flow
from utils.mirror_output import mirror_tutorial_output
from utils.profile_presets import PROFILE_REGISTRY, TRMMS_PROFILES

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


def main():
    parser = argparse.ArgumentParser(description="Generate a tutorial for a GitHub codebase or local directory.")

    source_group = parser.add_mutually_exclusive_group(required=False)
    source_group.add_argument("--repo", help="URL of the public GitHub repository.")
    source_group.add_argument("--dir", help="Path to local directory.")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_REGISTRY.keys()),
        help="Preset: TRMMS customer/admin/code (or trmms-* aliases). Sets input, output, and optional vault mirror.",
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

    if not args.repo and not args.dir and not args.profile:
        parser.error("One of --repo, --dir, or --profile is required")

    profile_preset = PROFILE_REGISTRY.get(args.profile) if args.profile else None
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
        github_token = args.token or os.environ.get('GITHUB_TOKEN')
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
        "final_output_dir": None
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
            profile=args.profile,
            input_dir=args.dir,
        )
    elif mirror_base and not final_dir:
        print("[mirror] Skipped: tutorial output path missing after generation.")


if __name__ == "__main__":
    main()
