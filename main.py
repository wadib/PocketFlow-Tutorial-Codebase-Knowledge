import dotenv
import os
import argparse
# Import the function that creates the flow
from flow import create_tutorial_flow

dotenv.load_dotenv(override=True)

TRMMS_REPO_ROOT = os.getenv(
    "TRMMS_REPO_ROOT",
    r"D:\coding\cursor_projects\TRMMS_Excel_New",
)

TRMMS_PROFILES = {
    "customer": {
        "local_dir": os.path.join(TRMMS_REPO_ROOT, "docs", "TRMMS_Excel_New_Manuals"),
        "include_patterns": {"*.md"},
        "exclude_patterns": {"*Checklist*", "*Glossary*"},
        "project_name": "TRMMS_Calculator_User_Manual",
        "output_dir": "./output/customer",
        "max_abstractions": 8,
    },
    "admin": {
        "local_dir": os.path.join(TRMMS_REPO_ROOT, "docs"),
        "include_patterns": {"*.md"},
        "exclude_patterns": {
            "TRMMS_Excel_New_Manuals/*",
            "memos/*",
            "reference/*",
        },
        "project_name": "TRMMS_Admin_Ops",
        "output_dir": "./output/admin",
        "max_abstractions": 10,
    },
    "code": {
        "local_dir": TRMMS_REPO_ROOT,
        "include_patterns": {"*.cs", "*.cshtml"},
        "exclude_patterns": {
            "*Migrations*",
            "bin/*",
            "obj/*",
            "*test*",
            ".git/*",
        },
        "project_name": "TRMMS_Excel_New",
        "output_dir": "./output/TRMMS",
        "max_abstractions": 14,
    },
}

# Default file patterns
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

# --- Main Function ---
def main():
    parser = argparse.ArgumentParser(description="Generate a tutorial for a GitHub codebase or local directory.")

    # Create mutually exclusive group for source
    source_group = parser.add_mutually_exclusive_group(required=False)
    source_group.add_argument("--repo", help="URL of the public GitHub repository.")
    source_group.add_argument("--dir", help="Path to local directory.")
    parser.add_argument(
        "--profile",
        choices=sorted(TRMMS_PROFILES.keys()),
        help="TRMMS preset: customer (user manual), admin (ops docs), code (developer tutorial).",
    )

    parser.add_argument("-n", "--name", help="Project name (optional, derived from repo/directory if omitted).")
    parser.add_argument("-t", "--token", help="GitHub personal access token (optional, reads from GITHUB_TOKEN env var if not provided).")
    parser.add_argument("-o", "--output", default="output", help="Base directory for output (default: ./output).")
    parser.add_argument("-i", "--include", nargs="+", help="Include file patterns (e.g. '*.py' '*.js'). Defaults to common code files if not specified.")
    parser.add_argument("-e", "--exclude", nargs="+", help="Exclude file patterns (e.g. 'tests/*' 'docs/*'). Defaults to test/build directories if not specified.")
    parser.add_argument("-s", "--max-size", type=int, default=100000, help="Maximum file size in bytes (default: 100000, about 100KB).")
    # Add language parameter for multi-language support
    parser.add_argument("--language", default="english", help="Language for the generated tutorial (default: english)")
    # Add use_cache parameter to control LLM caching
    parser.add_argument("--no-cache", action="store_true", help="Disable LLM response caching (default: caching enabled)")
    # Add max_abstraction_num parameter to control the number of abstractions
    parser.add_argument("--max-abstractions", type=int, default=None, help="Maximum number of abstractions to identify (default: 10, or profile preset)")

    args = parser.parse_args()

    if not args.repo and not args.dir and not args.profile:
        parser.error("One of --repo, --dir, or --profile is required")

    profile_preset = TRMMS_PROFILES.get(args.profile) if args.profile else None
    if profile_preset and not args.dir and not args.repo:
        args.dir = profile_preset["local_dir"]
    if profile_preset and not args.name:
        args.name = profile_preset["project_name"]
    if profile_preset and args.output == "output":
        args.output = profile_preset["output_dir"]

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

    # Get GitHub token from argument or environment variable if using repo
    github_token = None
    if args.repo:
        github_token = args.token or os.environ.get('GITHUB_TOKEN')
        if not github_token:
            print("Warning: No GitHub token provided. You might hit rate limits for public repositories.")

    # Initialize the shared dictionary with inputs
    shared = {
        "repo_url": args.repo,
        "local_dir": args.dir,
        "project_name": args.name, # Can be None, FetchRepo will derive it
        "github_token": github_token,
        "output_dir": args.output, # Base directory for CombineTutorial output

        # Add include/exclude patterns and max file size
        "include_patterns": include_patterns,
        "exclude_patterns": exclude_patterns,
        "max_file_size": args.max_size,

        # Add language for multi-language support
        "language": args.language,
        
        # Add use_cache flag (inverse of no-cache flag)
        "use_cache": not args.no_cache,
        
        # Add max_abstraction_num parameter
        "max_abstraction_num": max_abstractions,

        # Outputs will be populated by the nodes
        "files": [],
        "abstractions": [],
        "relationships": {},
        "chapter_order": [],
        "chapters": [],
        "final_output_dir": None
    }

    # Display starting message with repository/directory and language
    print(f"Starting tutorial generation for: {args.repo or args.dir} in {args.language.capitalize()} language")
    print(f"LLM caching: {'Disabled' if args.no_cache else 'Enabled'}")

    # Create the flow instance
    tutorial_flow = create_tutorial_flow()

    # Run the flow
    tutorial_flow.run(shared)

if __name__ == "__main__":
    main()
