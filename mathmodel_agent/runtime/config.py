"""Case layout and credential-free runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


DEFAULT_CASE_TOML = """# MathModel Agent case configuration. Do not put credentials here.
[runtime]
local_slots = 2
poll_interval = 0.25

[policy]
sandbox = "workspace-write"
allow_network = false
allowed_extra_write_paths = []

[profiles.default]
model = "gpt-5.6-terra"
effort = "high"
# codex_profile = "provider-profile-name"

[profiles.fast]
model = "gpt-5.6-luna"
effort = "medium"

[profiles.standard]
model = "gpt-5.6-terra"
effort = "high"

[profiles.full]
model = "gpt-5.6-sol"
effort = "high"

[tools]
# exa = "exa"
"""


CASE_DIRECTORIES = (
    "human",
    "problem",
    "datasets",
    "sources/raw",
    "sources/processed",
    "sources/notes",
    "knowledge",
    "freezes",
    "candidates",
    "comparisons",
    "tasks",
    "artifacts",
    "paper",
    ".runtime/receipts",
)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Profile:
    name: str
    model: str
    effort: str
    codex_profile: str | None = None


@dataclass(frozen=True)
class CaseConfig:
    case_root: Path
    local_slots: int
    poll_interval: float
    sandbox: str
    allow_network: bool
    allowed_extra_write_paths: tuple[Path, ...]
    profiles: dict[str, Profile]
    tools: dict[str, str]

    def profile(self, name: str) -> Profile:
        try:
            return self.profiles[name]
        except KeyError as exc:
            raise ConfigError(f"unknown case profile: {name}") from exc


def init_case(case_root: str | Path) -> Path:
    root = Path(case_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "case.toml"
    if config_path.exists():
        raise FileExistsError(f"case already initialized: {config_path}")
    for relative in CASE_DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_CASE_TOML, encoding="utf-8")
    return root


def load_case_config(case_root: str | Path) -> CaseConfig:
    root = Path(case_root).resolve()
    path = root / "case.toml"
    if not path.is_file():
        raise ConfigError(f"missing case configuration: {path}")
    with path.open("rb") as stream:
        raw = tomllib.load(stream)

    _reject_unknown(raw, {"runtime", "policy", "profiles", "tools"}, "case.toml")

    runtime = _mapping(raw.get("runtime"), "runtime")
    policy = _mapping(raw.get("policy"), "policy")
    raw_profiles = _mapping(raw.get("profiles"), "profiles")
    if not raw_profiles:
        raise ConfigError("case.toml must define at least one [profiles.<name>]")
    _reject_unknown(runtime, {"local_slots", "poll_interval"}, "runtime")
    _reject_unknown(policy, {"sandbox", "allow_network", "allowed_extra_write_paths"}, "policy")

    profiles: dict[str, Profile] = {}
    for name, value in raw_profiles.items():
        profile = _mapping(value, f"profiles.{name}")
        _reject_unknown(profile, {"model", "effort", "codex_profile"}, f"profiles.{name}")
        model = profile.get("model")
        effort = profile.get("effort")
        codex_profile = profile.get("codex_profile")
        if not isinstance(model, str) or not model:
            raise ConfigError(f"profiles.{name}.model must be a non-empty string")
        if not isinstance(effort, str) or not effort:
            raise ConfigError(f"profiles.{name}.effort must be a non-empty string")
        if effort not in {"low", "medium", "high", "xhigh", "max"}:
            raise ConfigError(f"profiles.{name}.effort is not supported")
        if codex_profile is not None and not isinstance(codex_profile, str):
            raise ConfigError(f"profiles.{name}.codex_profile must be a string")
        profiles[name] = Profile(name, model, effort, codex_profile)

    slots = runtime.get("local_slots", 2)
    poll = runtime.get("poll_interval", 0.25)
    if not isinstance(slots, int) or isinstance(slots, bool) or slots < 1:
        raise ConfigError("runtime.local_slots must be a positive integer")
    if not isinstance(poll, (int, float)) or isinstance(poll, bool) or poll <= 0:
        raise ConfigError("runtime.poll_interval must be positive")

    sandbox = policy.get("sandbox", "workspace-write")
    if sandbox not in {"read-only", "workspace-write", "danger-full-access"}:
        raise ConfigError("policy.sandbox is not a supported Codex sandbox")
    allow_network = policy.get("allow_network", False)
    if not isinstance(allow_network, bool):
        raise ConfigError("policy.allow_network must be boolean")

    extras = policy.get("allowed_extra_write_paths", [])
    if not isinstance(extras, list) or not all(isinstance(item, str) for item in extras):
        raise ConfigError("policy.allowed_extra_write_paths must be a string list")
    resolved_extras = tuple(_resolve_inside(root, item) for item in extras)

    raw_tools = _mapping(raw.get("tools", {}), "tools")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in raw_tools.items()):
        raise ConfigError("tools entries must map names to executable strings")

    return CaseConfig(
        case_root=root,
        local_slots=slots,
        poll_interval=float(poll),
        sandbox=sandbox,
        allow_network=allow_network,
        allowed_extra_write_paths=resolved_extras,
        profiles=profiles,
        tools=dict(raw_tools),
    )


def _mapping(value: object, name: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a TOML table")
    return value


def _reject_unknown(values: dict, allowed: set[str], name: str) -> None:
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ConfigError(f"unsupported {name} keys: {', '.join(unknown)}")


def _resolve_inside(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    if not candidate.is_relative_to(root):
        raise ConfigError(f"configured path escapes case root: {value}")
    return candidate
