#!/usr/bin/env python3
"""Validate this template or a copy using only Python's standard library."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
ROOT_AGENTS = "AGENTS.md"
PROJECT_AGENTS = "examples/project/AGENTS.md"
MAX_ROOT_BYTES = 6 * 1024
MAX_PROJECT_BYTES = 8 * 1024
MAX_CHAIN_BYTES = 24 * 1024

REQUIRED_MAP_TARGETS = {
    "AGENTS.md",
    "examples/project/AGENTS.md",
    ".codex/config.toml",
    ".codex/agents/explorer.toml",
    ".codex/agents/researcher.toml",
    ".codex/agents/worker.toml",
    "scripts/link_workspace.py",
    "scripts/validate_template.py",
    "scripts/export_template.py",
    "tests/test_link_workspace.py",
    "tests/test_validate_template.py",
    "tests/test_export_template.py",
    "docs/templates/task-state.md",
    "docs/templates/delegation.md",
    ".github/workflows/validate.yml",
}
OFFICIAL_LINKS = {
    "https://learn.chatgpt.com/docs/agent-configuration/agents-md",
    "https://learn.chatgpt.com/docs/config-file/config-basic",
    "https://learn.chatgpt.com/docs/agent-configuration/subagents",
}
KNOWN_REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra"}
UNIX_HOME_PATTERN = re.compile(r"/(?:home|Users)/[^/\\\s<>]+(?:/|\b)")
TILDE_HOME_PATTERN = re.compile(r"(?<![\w])~[A-Za-z0-9_.-]+(?:/|\\|\b)")
WINDOWS_HOME_PATTERN = re.compile(
    r"(?i)(?:\b[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s<>]+"
    r"(?:[\\/]|\b))"
)
EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
NEUTRAL_EMAIL_DOMAINS = {"example.com", "example.invalid"}
KNOWN_SECRET_PATTERN = re.compile(
    r"(?i)\b(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|"
    r"AIza[0-9A-Za-z_-]{30,})\b"
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"password|passwd|secret|token|private[_-]?key)\b\s*[:=]\s*['\"]?"
    r"(?P<value>[A-Za-z0-9_./+=-]{8,})"
)
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/-]{16,}={0,2})")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:OPENSSH|RSA|EC|DSA|PGP) PRIVATE KEY-----")
MARKDOWN_REFERENCE_PATTERN = re.compile(
    r"(?m)^ {0,3}\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))"
)
MARKDOWN_FENCE_PATTERN = re.compile(r"^ {0,3}(`{3,}|~{3,})")
INLINE_CODE_PATTERN = re.compile(r"(?<!`)`+[^`\n]*`+(?!`)")
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
}
WEIGHT_EXTENSIONS = {
    ".bin",
    ".ckpt",
    ".gguf",
    ".onnx",
    ".pt",
    ".pth",
    ".safetensors",
    ".tflite",
    ".weights",
}
DATABASE_EXTENSIONS = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-wal",
    ".db-shm",
    ".sqlite-wal",
    ".sqlite-shm",
    ".sqlite3-wal",
    ".sqlite3-shm",
}


def _without_markdown_code(text: str) -> str:
    visible_lines: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines():
        match = MARKDOWN_FENCE_PATTERN.match(line)
        if fence_character is None:
            if match:
                fence_character = match.group(1)[0]
                fence_length = len(match.group(1))
                continue
            visible_lines.append(line)
        elif match and match.group(1)[0] == fence_character and len(match.group(1)) >= fence_length:
            fence_character = None
            fence_length = 0
    return INLINE_CODE_PATTERN.sub("", "\n".join(visible_lines))


def _inline_link_destinations(text: str) -> list[str]:
    """Read simple CommonMark inline links, respecting escapes and nested parentheses."""
    destinations: list[str] = []
    cursor = 0
    while True:
        marker = text.find("](", cursor)
        if marker < 0:
            break
        open_index = marker + 1
        index = open_index + 1
        depth = 0
        escaped = False
        close_index = -1
        while index < len(text):
            character = text[index]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                if depth == 0:
                    close_index = index
                    break
                depth -= 1
            index += 1
        if close_index < 0:
            cursor = marker + 2
            continue

        content = text[open_index + 1 : close_index].lstrip()
        if content.startswith("<"):
            end = content.find(">")
            if end > 0:
                destinations.append(content[1:end])
        else:
            end = 0
            depth = 0
            escaped = False
            while end < len(content):
                character = content[end]
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == "(":
                    depth += 1
                elif character == ")" and depth:
                    depth -= 1
                elif character.isspace() and depth == 0:
                    break
                end += 1
            if end:
                destinations.append(content[:end].replace("\\ ", " "))
        cursor = close_index + 1
    return destinations


def _markdown_destinations(text: str) -> list[str]:
    text = _without_markdown_code(text)
    destinations = _inline_link_destinations(text)
    for match in MARKDOWN_REFERENCE_PATTERN.finditer(text):
        destinations.append(match.group(1) or match.group(2))
    return destinations


def _markdown_targets(root: Path, relative_file: str, errors: list[str]) -> set[str]:
    path = root / relative_file
    if not path.is_file() or path.is_symlink():
        return set()
    targets: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{relative_file}: cannot read Markdown: {exc}")
        return targets

    for raw_target in _markdown_destinations(text):
        target = unquote(raw_target.strip())
        if not target:
            continue
        if target.startswith("//") and not target.startswith("///"):
            continue
        if re.match(r"^[A-Za-z]:[\\/]", target):
            errors.append(f"{relative_file}: local link must be relative: {target}")
            continue
        scheme = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
        if scheme:
            if scheme.group(0).lower() != "file:":
                continue
            errors.append(f"{relative_file}: local file link must be relative: {target}")
            continue
        target_path = target.split("#", 1)[0].split("?", 1)[0]
        if not target_path:
            continue
        if re.match(r"^[A-Za-z]:[\\/]", target_path):
            errors.append(f"{relative_file}: local link must be relative: {target}")
            continue
        candidate = Path(target_path)
        if candidate.is_absolute():
            errors.append(f"{relative_file}: local link must be relative: {target}")
            continue
        try:
            resolved = (path.parent / candidate).resolve(strict=False)
        except (OSError, RuntimeError):
            errors.append(f"{relative_file}: cannot safely resolve local link: {target}")
            continue
        try:
            resolved.relative_to(root)
        except ValueError:
            errors.append(f"{relative_file}: local link escapes template root: {target}")
            continue
        if not resolved.exists():
            errors.append(f"{relative_file}: missing local link target: {target}")
            continue
        targets.add(resolved.relative_to(root).as_posix())
    return targets


def _check_toml(root: Path, errors: list[str]) -> None:
    config_path = root / ".codex/config.toml"
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f".codex/config.toml: cannot parse TOML: {exc}")
        return

    _check_nonempty_string(config, "model", ".codex/config.toml", errors)
    _check_effort(config, "model_reasoning_effort", ".codex/config.toml", errors)
    agents_config = config.get("agents")
    if not isinstance(agents_config, dict):
        errors.append(".codex/config.toml: [agents] table is required")
    else:
        if not isinstance(agents_config.get("enabled"), bool):
            errors.append(".codex/config.toml: [agents].enabled must be a boolean")
        concurrency = agents_config.get("max_concurrent_threads_per_session")
        if type(concurrency) is not int or concurrency < 1:
            errors.append(".codex/config.toml: [agents].max_concurrent_threads_per_session must be a positive integer")
        depth = agents_config.get("max_depth")
        if type(depth) is not int or depth < 1:
            errors.append(".codex/config.toml: [agents].max_depth must be a positive integer")
        _check_nonempty_string(
            agents_config, "default_subagent_model", ".codex/config.toml [agents]", errors
        )
        _check_effort(
            agents_config,
            "default_subagent_reasoning_effort",
            ".codex/config.toml [agents]",
            errors,
        )

    for role in ("explorer", "researcher", "worker"):
        relative = f".codex/agents/{role}.toml"
        path = root / relative
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{relative}: cannot parse TOML: {exc}")
            continue
        if data.get("name") != role:
            errors.append(f"{relative}: name must match the {role!r} role")
        for key in ("description", "model", "developer_instructions"):
            _check_nonempty_string(data, key, relative, errors)
        _check_effort(data, "model_reasoning_effort", relative, errors)
        if "model_verbosity" in data:
            _check_nonempty_string(data, "model_verbosity", relative, errors)


def _check_nonempty_string(
    data: dict, key: str, context: str, errors: list[str]
) -> None:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}: {key} must be a non-empty string")


def _check_effort(data: dict, key: str, context: str, errors: list[str]) -> None:
    value = data.get(key)
    if not isinstance(value, str) or value not in KNOWN_REASONING_EFFORTS:
        errors.append(
            f"{context}: {key} must use a recognized reasoning-effort spelling "
            f"({', '.join(sorted(KNOWN_REASONING_EFFORTS))})"
        )


def _walk_paths(root: Path):
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in directories:
            path = current_path / name
            if name in SKIP_DIRS:
                continue
            if path.is_symlink():
                yield path
                continue
            kept_directories.append(name)
            yield path
        directories[:] = kept_directories
        for name in files:
            yield current_path / name


def _text_files(root: Path):
    for path in _walk_paths(root):
        if path.is_symlink() or not path.is_file():
            continue
        yield path


def _placeholder_value(value: str) -> bool:
    normalized = value.strip().strip("\"'").strip().lower()
    if not normalized:
        return True
    if normalized.startswith(("<", "${", "your_", "your-", "replace_", "replace-")):
        return True
    return normalized in {
        "changeme",
        "change_me",
        "dummy",
        "example",
        "none",
        "null",
        "placeholder",
        "sample",
        "test",
    }


def _contains_credentials(text: str) -> bool:
    if KNOWN_SECRET_PATTERN.search(text) or PRIVATE_KEY_PATTERN.search(text):
        return True
    for pattern in (SECRET_ASSIGNMENT_PATTERN, BEARER_PATTERN):
        for match in pattern.finditer(text):
            value = match.groupdict().get("value") or match.group(1)
            if not _placeholder_value(value):
                return True
    return False


def _contains_personal_email(text: str) -> bool:
    for address in EMAIL_PATTERN.findall(text):
        domain = address.rsplit("@", 1)[1].lower()
        if domain not in NEUTRAL_EMAIL_DOMAINS:
            return True
    return False


def _has_environment_values(path: Path) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return True
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.lower().startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            return True
        _, value = stripped.split("=", 1)
        if not _placeholder_value(value):
            return True
    return False


def _runtime_artifact_findings(root: Path) -> list[str]:
    findings: list[str] = []
    tasks = root / ".codex/tasks"
    if os.path.lexists(tasks):
        if tasks.is_symlink() or not tasks.is_dir():
            findings.append(".codex/tasks: contains private task state")
        else:
            try:
                has_entries = next(tasks.iterdir(), None) is not None
            except OSError:
                has_entries = True
            if has_entries:
                findings.append(".codex/tasks: contains private task state")

    env_examples = {".env.example", ".env.sample", ".env.template"}
    for path in _walk_paths(root):
        relative = path.relative_to(root).as_posix()
        parts = tuple(part.lower() for part in path.relative_to(root).parts)
        name = path.name.lower()
        suffix = path.suffix.lower()
        if name in {"auth.json", "credentials.json"}:
            findings.append(f"{relative}: authentication state must not be included")
        if name.startswith(".env") and name not in env_examples:
            if path.is_symlink() or (path.is_file() and _has_environment_values(path)):
                findings.append(f"{relative}: environment file contains values")
        if any(len(parts) >= 2 and parts[index : index + 2] == (".codex", "tasks") for index in range(len(parts) - 1)):
            if relative != ".codex/tasks":
                findings.append(f"{relative}: private task state must not be included")
        if suffix in DATABASE_EXTENSIONS or suffix in WEIGHT_EXTENSIONS:
            findings.append(f"{relative}: runtime database or model artifact must not be included")
        if suffix in {".log", ".session"}:
            findings.append(f"{relative}: runtime log or session state must not be included")
        if suffix in {".jsonl", ".ndjson"} and (
            name.startswith(("session", "rollout"))
            or any(part in {"session", "sessions", "rollouts"} for part in parts[:-1])
        ):
            findings.append(f"{relative}: session log must not be included")
    return findings


def validate(root_value: str | Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        root = Path(root_value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return [f"template root cannot be resolved: {exc}"]
    if not root.is_dir():
        return [f"template root is not a directory: {root}"]

    required_paths = {
        "README.md",
        ROOT_AGENTS,
        PROJECT_AGENTS,
        ".codex/config.toml",
        ".codex/agents/explorer.toml",
        ".codex/agents/researcher.toml",
        ".codex/agents/worker.toml",
        "scripts/link_workspace.py",
        "scripts/validate_template.py",
        "scripts/export_template.py",
        "tests/test_link_workspace.py",
        "tests/test_validate_template.py",
        "tests/test_export_template.py",
        "docs/templates/task-state.md",
        "docs/templates/delegation.md",
        ".github/workflows/validate.yml",
        ".gitignore",
        "LICENSE",
    }
    for relative in sorted(required_paths):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            errors.append(f"required regular file is missing: {relative}")

    root_agents = root / ROOT_AGENTS
    project_agents = root / PROJECT_AGENTS
    if root_agents.is_file():
        root_size = root_agents.stat().st_size
        if root_size > MAX_ROOT_BYTES:
            errors.append(f"{ROOT_AGENTS} is {root_size} bytes; limit is {MAX_ROOT_BYTES}")
    else:
        root_size = 0
    if project_agents.is_file():
        project_size = project_agents.stat().st_size
        if project_size > MAX_PROJECT_BYTES:
            errors.append(f"{PROJECT_AGENTS} is {project_size} bytes; limit is {MAX_PROJECT_BYTES}")
    else:
        project_size = 0
    if root_size + project_size > MAX_CHAIN_BYTES:
        errors.append(
            f"example instruction chain is {root_size + project_size} bytes; limit is {MAX_CHAIN_BYTES}"
        )

    markdown_targets: dict[str, set[str]] = {}
    for path in _text_files(root):
        if path.suffix.lower() == ".md":
            relative = path.relative_to(root).as_posix()
            markdown_targets[relative] = _markdown_targets(root, relative, errors)

    readme_targets = markdown_targets.get("README.md", set())
    missing_map = sorted(REQUIRED_MAP_TARGETS - readme_targets)
    if missing_map:
        errors.append("README.md is missing relative map links for: " + ", ".join(missing_map))
    root_targets = markdown_targets.get(ROOT_AGENTS, set())
    if PROJECT_AGENTS not in root_targets:
        errors.append(f"{ROOT_AGENTS} must link to {PROJECT_AGENTS}")

    readme_path = root / "README.md"
    if readme_path.is_file():
        readme = readme_path.read_text(encoding="utf-8")
        for link in sorted(OFFICIAL_LINKS):
            if link not in readme:
                errors.append(f"README.md is missing official reference: {link}")

    _check_toml(root, errors)

    for path in _text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        if (
            UNIX_HOME_PATTERN.search(text)
            or TILDE_HOME_PATTERN.search(text)
            or WINDOWS_HOME_PATTERN.search(text)
        ):
            errors.append(f"{relative}: contains a user-specific home path")
        if _contains_personal_email(text):
            errors.append(f"{relative}: contains a literal email address")
        if _contains_credentials(text):
            errors.append(f"{relative}: appears to contain a credential")
    errors.extend(_runtime_artifact_findings(root))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="template root to validate")
    args = parser.parse_args(argv)
    errors = validate(args.root)
    if errors:
        print("Template validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Template validation passed: {Path(args.root).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
