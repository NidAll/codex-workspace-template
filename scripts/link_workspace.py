#!/usr/bin/env python3
"""Link shared workspace Codex defaults into explicitly named nested projects."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path


class LinkError(Exception):
    """A preflight or filesystem operation failed safely."""


@dataclass(frozen=True)
class Link:
    destination: Path
    target: Path
    target_text: str
    is_directory: bool
    already_linked: bool


@dataclass(frozen=True)
class ProjectPlan:
    project: Path
    codex_dir: Path
    create_codex_dir: bool
    links: tuple[Link, ...]


def _exists(path: Path) -> bool:
    return os.path.lexists(path)


def _canonical_sources(workspace: str | Path) -> tuple[Path, Path, Path]:
    try:
        root = Path(workspace).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LinkError(f"workspace does not exist or cannot be resolved: {workspace}") from exc
    if not root.is_dir():
        raise LinkError(f"workspace is not a directory: {root}")

    home = Path.home().resolve()
    if root == home or root == home / ".codex":
        raise LinkError("workspace cannot be the home directory or global Codex directory")

    codex_dir = root / ".codex"
    if codex_dir.is_symlink():
        raise LinkError(f"canonical .codex directory must not be a symlink: {codex_dir}")
    if not codex_dir.is_dir():
        raise LinkError(f"canonical .codex directory is missing: {codex_dir}")

    config = codex_dir / "config.toml"
    agents = codex_dir / "agents"
    if config.is_symlink() or not config.is_file():
        raise LinkError(f"canonical config.toml must be a regular file: {config}")
    if agents.is_symlink() or not agents.is_dir():
        raise LinkError(f"canonical agents must be a real directory: {agents}")
    return root, config, agents


def _project_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        project = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LinkError(f"project directory does not exist or cannot be resolved: {value}") from exc
    if not project.is_dir():
        raise LinkError(f"project is not a directory: {project}")
    try:
        project.relative_to(root)
    except ValueError as exc:
        raise LinkError(f"project must resolve inside the workspace: {project}") from exc
    if project == root:
        raise LinkError("the canonical workspace root cannot also be a linked project")
    try:
        project.relative_to(root / ".codex")
    except ValueError:
        pass
    else:
        raise LinkError("a project cannot be inside the canonical .codex directory")
    return project


def _plan_link(destination: Path, target: Path, *, is_directory: bool) -> Link:
    target_text = os.path.relpath(target, start=destination.parent)
    if not _exists(destination):
        return Link(destination, target, target_text, is_directory, False)
    if destination.is_symlink():
        existing_target = os.readlink(destination)
        if existing_target == target_text:
            return Link(destination, target, target_text, is_directory, True)
        raise LinkError(
            f"conflicting symlink at {destination}: points to {existing_target!r}, "
            f"expected {target_text!r}"
        )
    raise LinkError(f"refusing to replace existing file or directory: {destination}")


def build_plans(workspace: str | Path, projects: list[str]) -> list[ProjectPlan]:
    root, config, agents = _canonical_sources(workspace)
    plans: list[ProjectPlan] = []
    seen: set[Path] = set()
    for value in projects:
        project = _project_path(root, value)
        if project in seen:
            raise LinkError(f"project was listed more than once: {project}")
        seen.add(project)

        codex_dir = project / ".codex"
        if codex_dir.is_symlink():
            raise LinkError(f"project .codex directory must not be a symlink: {codex_dir}")
        if _exists(codex_dir) and not codex_dir.is_dir():
            raise LinkError(f"project .codex path is not a directory: {codex_dir}")

        links = (
            _plan_link(codex_dir / "config.toml", config, is_directory=False),
            _plan_link(codex_dir / "agents", agents, is_directory=True),
        )
        plans.append(ProjectPlan(project, codex_dir, not _exists(codex_dir), links))
    return plans


def _apply(plans: list[ProjectPlan]) -> None:
    created_directories: list[Path] = []
    created_links: list[Link] = []
    try:
        for plan in plans:
            if plan.create_codex_dir:
                plan.codex_dir.mkdir()
                created_directories.append(plan.codex_dir)
            for link in plan.links:
                if link.already_linked:
                    continue
                os.symlink(
                    link.target_text,
                    link.destination,
                    target_is_directory=link.is_directory,
                )
                created_links.append(link)
    except OSError as exc:
        rollback_errors: list[str] = []
        for link in reversed(created_links):
            try:
                if link.destination.is_symlink() and os.readlink(link.destination) == link.target_text:
                    link.destination.unlink()
            except OSError as rollback_exc:
                rollback_errors.append(f"{link.destination}: {rollback_exc}")
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                # Preserve anything another process placed there after preflight.
                pass
        details = f"failed to create links: {exc}"
        if rollback_errors:
            details += "; rollback could not remove " + ", ".join(rollback_errors)
        raise LinkError(details) from exc


def _describe(plans: list[ProjectPlan], *, apply: bool) -> None:
    mode = "APPLY" if apply else "PREVIEW (no files changed)"
    print(mode)
    for plan in plans:
        print(f"{plan.project}")
        if plan.create_codex_dir:
            print(f"  create {plan.codex_dir}")
        for link in plan.links:
            if link.already_linked:
                print(f"  already linked {link.destination}")
            elif apply:
                print(f"  linked {link.destination} -> {link.target_text}")
            else:
                print(f"  link {link.destination} -> {link.target_text}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="canonical workspace directory")
    parser.add_argument("--apply", action="store_true", help="create the planned relative symlinks")
    parser.add_argument("projects", nargs="+", help="explicit project paths, relative to the workspace or absolute inside it")
    args = parser.parse_args(argv)

    try:
        plans = build_plans(args.workspace, args.projects)
        if args.apply:
            _apply(plans)
        _describe(plans, apply=args.apply)
    except LinkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
