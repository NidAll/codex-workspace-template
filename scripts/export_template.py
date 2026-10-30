#!/usr/bin/env python3
"""Export a validated ZIP of committed template files from Git HEAD."""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from validate_template import SKIP_DIRS, validate


ROOT = Path(__file__).resolve().parents[1]
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
EXCLUDED_CACHE_SUFFIXES = {".pyc", ".pyo"}


class ExportError(Exception):
    """An unsafe or invalid export request."""


@dataclass(frozen=True)
class GitEntry:
    path: str
    mode: int
    object_id: str


@dataclass(frozen=True)
class ExportResult:
    output: Path
    commit: str
    file_count: int


def _git(root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ExportError("Git is required to export committed files") from exc
    if result.returncode:
        details = result.stderr.decode("utf-8", errors="replace").strip()
        raise ExportError(details or f"Git command failed: {' '.join(arguments)}")
    return result.stdout


def _repository_root(source: str | Path) -> tuple[Path, str]:
    try:
        root = Path(source).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExportError(f"source repository cannot be resolved: {source}") from exc
    if not root.is_dir():
        raise ExportError(f"source is not a directory: {source}")
    try:
        git_root = Path(_git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
        commit = _git(root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ExportError("Git returned an invalid repository path or commit ID") from exc
    if git_root != root:
        raise ExportError("source must be the repository root")
    if not OBJECT_ID_PATTERN.fullmatch(commit):
        raise ExportError("Git returned an invalid HEAD commit ID")
    return root, commit


def _safe_repo_path(raw_path: bytes) -> str:
    try:
        path = raw_path.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExportError("Git contains a path that is not valid UTF-8") from exc
    parts = path.split("/")
    if (
        not path
        or path.startswith("/")
        or "\\" in path
        or re.match(r"^[A-Za-z]:", path)
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ExportError(f"Git contains a non-portable or unsafe path: {path!r}")
    return path


def _tree_entries(root: Path, commit: str) -> list[GitEntry]:
    raw_tree = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit)
    entries: list[GitEntry] = []
    seen: set[str] = set()
    casefolded: set[str] = set()
    for record in raw_tree.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode_bytes, kind, object_id_bytes = metadata.split(b" ", 2)
            path = _safe_repo_path(raw_path)
            mode = int(mode_bytes, 8)
            object_id = object_id_bytes.decode("ascii")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ExportError("Git returned a malformed tree entry") from exc

        if any(part in SKIP_DIRS for part in path.split("/")):
            continue
        if PurePosixPath(path).suffix.lower() in EXCLUDED_CACHE_SUFFIXES:
            continue
        if path in seen or path.casefold() in casefolded:
            raise ExportError(f"Git contains duplicate or case-colliding paths: {path!r}")
        seen.add(path)
        casefolded.add(path.casefold())
        if kind != b"blob" or mode not in {0o100644, 0o100755}:
            if mode == 0o120000:
                raise ExportError(f"tracked symlinks are not exportable: {path}")
            raise ExportError(f"unsupported tracked entry type or mode: {path}")
        if not OBJECT_ID_PATTERN.fullmatch(object_id):
            raise ExportError(f"Git returned an invalid object ID for {path}")
        entries.append(GitEntry(path, mode, object_id))
    if not entries:
        raise ExportError("HEAD contains no exportable files")
    return sorted(entries, key=lambda entry: entry.path)


def _write_committed_snapshot(root: Path, entries: list[GitEntry], destination: Path) -> None:
    for entry in entries:
        data = _git(root, "cat-file", "blob", entry.object_id)
        path = destination.joinpath(*PurePosixPath(entry.path).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o755 if entry.mode == 0o100755 else 0o644)


def _check_snapshot(snapshot: Path, description: str) -> None:
    errors = validate(snapshot)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise ExportError(f"{description} failed template validation:\n{details}")


def _destination_path(output: str | Path, source_root: Path) -> Path:
    candidate = Path(output).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if not candidate.name or candidate.name in {".", ".."}:
        raise ExportError("output must name a ZIP file")
    try:
        parent = candidate.parent.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExportError("output parent directory must already exist") from exc
    if not parent.is_dir():
        raise ExportError("output parent must be a directory")
    destination = parent / candidate.name
    try:
        destination.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ExportError("output must be outside the source repository")
    if os.path.lexists(destination):
        raise ExportError("output already exists; refusing to overwrite it")
    return destination


def _zip_snapshot(snapshot: Path, entries: list[GitEntry], archive_path: Path) -> None:
    mode_by_path = {entry.path: entry.mode for entry in entries}
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        archive.comment = b""
        for relative in sorted(mode_by_path):
            info = zipfile.ZipInfo(relative, date_time=ZIP_DATE)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits = 0x800
            permissions = 0o755 if mode_by_path[relative] == 0o100755 else 0o644
            info.external_attr = (stat.S_IFREG | permissions) << 16
            info.extra = b""
            info.comment = b""
            archive.writestr(
                info,
                (snapshot / relative).read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def _extract_and_validate(archive_path: Path, extraction_root: Path, expected: set[str]) -> None:
    seen: set[str] = set()
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            for info in archive.infolist():
                path = _safe_repo_path(info.filename.encode("utf-8"))
                if info.is_dir():
                    raise ExportError(f"unexpected directory entry in archive: {path}")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise ExportError(f"unexpected symlink entry in archive: {path}")
                if path in seen:
                    raise ExportError(f"duplicate archive path: {path}")
                seen.add(path)
                target = extraction_root.joinpath(*PurePosixPath(path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ExportError(f"temporary ZIP could not be safely verified: {exc}") from exc
    if seen != expected:
        raise ExportError("temporary ZIP file list differs from committed HEAD")
    _check_snapshot(extraction_root, "temporary ZIP extraction")


def export_template(source: str | Path, output: str | Path) -> ExportResult:
    """Export only validated, committed HEAD files to a new deterministic ZIP."""
    root, commit = _repository_root(source)
    destination = _destination_path(output, root)
    entries = _tree_entries(root, commit)
    expected = {entry.path for entry in entries}
    temporary_archive: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="codex-template-source-") as source_temp:
            snapshot = Path(source_temp) / "snapshot"
            snapshot.mkdir()
            _write_committed_snapshot(root, entries, snapshot)
            _check_snapshot(snapshot, "committed HEAD")

            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
            )
            os.close(descriptor)
            temporary_archive = Path(temporary_name)
            _zip_snapshot(snapshot, entries, temporary_archive)
            with tempfile.TemporaryDirectory(prefix="codex-template-check-") as check_temp:
                extraction = Path(check_temp) / "extracted"
                extraction.mkdir()
                _extract_and_validate(temporary_archive, extraction, expected)

        try:
            os.link(temporary_archive, destination)
        except FileExistsError as exc:
            raise ExportError("output appeared during export; refusing to overwrite it") from exc
        except OSError as exc:
            raise ExportError(f"could not atomically publish ZIP at destination: {exc}") from exc
        return ExportResult(destination, commit, len(entries))
    except ExportError:
        raise
    except OSError as exc:
        raise ExportError(f"export failed: {exc}") from exc
    finally:
        if temporary_archive is not None:
            try:
                temporary_archive.unlink(missing_ok=True)
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ROOT), help="Git repository root; exports committed HEAD only")
    parser.add_argument("--output", required=True, help="new ZIP path outside the source repository")
    args = parser.parse_args(argv)
    try:
        result = export_template(args.source, args.output)
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Exported {result.file_count} committed files from {result.commit} to {result.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
