"""Profile presets loaded from POCKETFLOW_PROJECT_CONFIG / --project-config."""

from utils.project_config import load_profiles_from_config, load_project_config

__all__ = ["load_profile_registry", "get_profile"]


def load_profile_registry(config_path: str | None = None) -> dict[str, dict]:
    cfg = load_project_config(config_path)
    if not cfg:
        return {}
    return load_profiles_from_config(cfg)


def get_profile(name: str, config_path: str | None = None) -> dict | None:
    return load_profile_registry(config_path).get(name)
