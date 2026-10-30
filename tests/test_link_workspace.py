from __future__ import annotations

import os
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/link_workspace.py"
sys.path.insert(0, str(SCRIPT.parent))
from link_workspace import LinkError, _apply, build_plans, main


class LinkWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.workspace = self.base / "canonical workspace"
        (self.workspace / ".codex/agents").mkdir(parents=True)
        (self.workspace / ".codex/config.toml").write_text('model = "test"\n', encoding="utf-8")
        (self.workspace / ".codex/agents/explorer.toml").write_text('name = "explorer"\n', encoding="utf-8")
        self.project = self.workspace / "project with spaces"
        self.project.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_link(self, *projects: str, apply: bool = False) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(SCRIPT), "--workspace", str(self.workspace)]
        if apply:
            command.append("--apply")
        command.extend(projects)
        return subprocess.run(command, text=True, capture_output=True, check=False)

    def test_default_preview_handles_spaces_without_mutating(self) -> None:
        result = self.run_link("project with spaces")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PREVIEW (no files changed)", result.stdout)
        self.assertIn("../../.codex/config.toml", result.stdout)
        self.assertFalse((self.project / ".codex").exists())

    def test_apply_uses_relative_symlinks_and_is_idempotent(self) -> None:
        first = self.run_link("project with spaces", apply=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        config_link = self.project / ".codex/config.toml"
        agents_link = self.project / ".codex/agents"
        self.assertTrue(config_link.is_symlink())
        self.assertTrue(agents_link.is_symlink())
        self.assertFalse(os.path.isabs(os.readlink(config_link)))
        self.assertEqual(config_link.resolve(), self.workspace / ".codex/config.toml")
        self.assertEqual(agents_link.resolve(), self.workspace / ".codex/agents")

        second = self.run_link("project with spaces", apply=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already linked", second.stdout)

    def test_missing_project_fails_without_creating_anything(self) -> None:
        result = self.run_link("missing-project", apply=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)
        self.assertFalse((self.workspace / "missing-project").exists())

    def test_missing_canonical_target_fails_without_partial_project_setup(self) -> None:
        (self.workspace / ".codex/agents/explorer.toml").unlink()
        (self.workspace / ".codex/agents").rmdir()
        result = self.run_link("project with spaces", apply=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / ".codex").exists())

    def test_agent_conflict_is_detected_before_config_link_is_created(self) -> None:
        project_codex = self.project / ".codex"
        project_codex.mkdir()
        conflict = project_codex / "agents"
        conflict.mkdir()
        (conflict / "local.toml").write_text('name = "local"\n', encoding="utf-8")

        result = self.run_link("project with spaces", apply=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to replace", result.stderr)
        self.assertFalse((project_codex / "config.toml").exists())
        self.assertTrue((conflict / "local.toml").is_file())

    def test_outside_workspace_project_is_rejected(self) -> None:
        outside = self.base / "outside project"
        outside.mkdir()
        result = self.run_link(str(outside), apply=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the workspace", result.stderr)
        self.assertFalse((outside / ".codex").exists())

    def test_symlinked_project_escaping_workspace_is_rejected(self) -> None:
        outside = self.base / "outside project"
        outside.mkdir()
        escaped = self.workspace / "escaped project"
        escaped.symlink_to(outside, target_is_directory=True)

        result = self.run_link("escaped project", apply=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the workspace", result.stderr)
        self.assertFalse((outside / ".codex").exists())

    def test_symlink_project_codex_directory_is_rejected_without_following_it(self) -> None:
        outside = self.base / "protected config"
        outside.mkdir()
        (outside / "sentinel").write_text("keep", encoding="utf-8")
        (self.project / ".codex").symlink_to(outside, target_is_directory=True)

        result = self.run_link("project with spaces", apply=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not be a symlink", result.stderr)
        self.assertEqual((outside / "sentinel").read_text(encoding="utf-8"), "keep")
        self.assertFalse((outside / "config.toml").exists())

    def test_write_failure_rolls_back_new_links_and_created_directory(self) -> None:
        plans = build_plans(self.workspace, ["project with spaces"])
        real_symlink = os.symlink
        calls = 0

        def fail_second_link(target: str, destination: str | Path, *, target_is_directory: bool = False) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected link failure")
            real_symlink(target, destination, target_is_directory=target_is_directory)

        with mock.patch("link_workspace.os.symlink", side_effect=fail_second_link):
            with self.assertRaisesRegex(LinkError, "injected link failure"):
                _apply(plans)

        self.assertFalse((self.project / ".codex").exists())

    def test_failed_apply_does_not_report_links_as_applied(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch("link_workspace._apply", side_effect=LinkError("injected failure")):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main(["--workspace", str(self.workspace), "--apply", "project with spaces"])

        self.assertEqual(result, 2)
        self.assertNotIn("linked", stdout.getvalue())
        self.assertIn("injected failure", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
