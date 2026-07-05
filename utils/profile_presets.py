"""Optional project profile presets. TRMMS profiles live here; add other projects as needed."""

import os

TRMMS_REPO_ROOT = os.getenv(
    "TRMMS_REPO_ROOT",
    r"D:\coding\cursor_projects\TRMMS_Excel_New",
)

HERMESVAULT_ROOT = os.getenv(
    "HERMESVAULT_ROOT",
    r"D:\OBSIDIAN MAIN\HermesVault",
)


def _vault_draft_dir(*relative_parts: str) -> str:
    return os.path.join(HERMESVAULT_ROOT, *relative_parts, "PocketFlow-Drafts")


TRMMS_PROFILES = {
    "customer": {
        "local_dir": os.path.join(TRMMS_REPO_ROOT, "docs", "TRMMS_Excel_New_Manuals"),
        "include_patterns": {"*.md"},
        "exclude_patterns": {"*Checklist*", "*Glossary*"},
        "project_name": "TRMMS_Calculator_User_Manual",
        "output_dir": "./output/customer",
        "mirror_output_dir": _vault_draft_dir("04-Projects", "TRMMS_Excel_New", "Manuals"),
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
        "mirror_output_dir": _vault_draft_dir("04-Projects", "TRMMS_Excel_New", "Sources"),
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
        "mirror_output_dir": _vault_draft_dir("04-Projects", "TRMMS_Excel_New", "Research"),
        "max_abstractions": 14,
    },
}

PROFILE_REGISTRY = {
    **{f"trmms-{key}": value for key, value in TRMMS_PROFILES.items()},
    **TRMMS_PROFILES,
}
