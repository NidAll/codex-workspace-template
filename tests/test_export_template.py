from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_template import ExportError, export_template
from validate_template import ROOT, SKIP_DIRS


class ExportTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "portable template"
        shutil.copytree(ROOT, self.repo, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        hooks = self.base / "empty fixture hooks"
        hooks.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Template Test Maintainers")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.symlinks", "true")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(hooks))
        (self.repo / "__pycache__").mkdir()
        (self.repo / "__pycache__/tracked.pyc").write_bytes(b"cache")
        (self.repo / ".venv/lib").mkdir(parents=True)
        (self.repo / ".venv/lib/tracked-runtime").write_text("runtime", encoding="utf-8")
        self.git("add", "-A")
        self.git("add", "-f", "__pycache__/tracked.pyc", ".venv/lib/tracked-runtime")
        self.git("commit", "-m", "initial template")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            self.fail(f"Git fixture setup failed: {' '.join(arguments)}\n{result.stderr}")
        return result

    def test_export_contains_only_committed_files_and_is_deterministic(self) -> None:
        (self.repo / "untracked.md").write_text("local only", encoding="utf-8")
        task = self.repo / ".codex/tasks/resume.md"
        task.parent.mkdir(parents=True)
        task.write_text("private checkpoint", encoding="utf-8")
        (self.repo / ".codex/auth.json").write_text("{}", encoding="utf-8")
        (self.repo / ".env").write_text("MODE=local\n", encoding="utf-8")
        (self.repo / "__pycache__/cache.pyc").write_bytes(b"cache")
        (self.repo / ".venv/lib/private").write_text("runtime", encoding="utf-8")

        first = self.base / "review.zip"
        second = self.base / "second review.zip"
        result = export_template(self.repo, first)
        export_template(self.repo, second)

        with zipfile.ZipFile(first) as archive:
            names = archive.namelist()
            self.assertEqual(result.file_count, len(names))
            self.assertIn("README.md", names)
            self.assertIn("scripts/export_template.py", names)
            self.assertFalse(any(name.startswith(".git/") for name in names))
            for excluded in (
                "untracked.md",
                ".codex/tasks/resume.md",
                ".codex/auth.json",
                ".env",
                "__pycache__/tracked.pyc",
                "__pycache__/cache.pyc",
                ".venv/lib/tracked-runtime",
                ".venv/lib/private",
            ):
                self.assertNotIn(excluded, names)
            tracked_paths = self.git("ls-tree", "-rz", "--name-only", "HEAD").stdout.split("\0")
            self.assertGreater(len(tracked_paths) - 1, len(names))
            self.assertTrue(all(not name.startswith(("/", "..")) for name in names))
            self.assertTrue(all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist()))
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertNotIn(self.repo.as_posix().encode(), first.read_bytes())

    def test_cli_defaults_to_its_repository_root(self) -> None:
        output = self.base / "cli review.zip"
        script = self.repo / "scripts/export_template.py"
        result = subprocess.run(
            [sys.executable, str(script), "--output", str(output)],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.is_file())
        self.assertIn("committed files", result.stdout)

    def test_destination_must_be_outside_source_and_must_not_exist(self) -> None:
        with self.assertRaisesRegex(ExportError, "outside the source"):
            export_template(self.repo, self.repo / "inside.zip")

        existing = self.base / "existing.zip"
        existing.write_bytes(b"preserve")
        with self.assertRaisesRegex(ExportError, "already exists"):
            export_template(self.repo, existing)
        self.assertEqual(existing.read_bytes(), b"preserve")

    def test_tracked_environment_values_are_refused(self) -> None:
        (self.repo / ".env").write_text("MODE=release\n", encoding="utf-8")
        self.git("add", "-f", ".env")
        self.git("commit", "-m", "add runtime environment")
        output = self.base / "must-not-exist.zip"

        with self.assertRaisesRegex(ExportError, "environment file contains values"):
            export_template(self.repo, output)
        self.assertFalse(output.exists())

    def test_tracked_symlink_is_refused(self) -> None:
        (self.repo / "README-link.md").symlink_to("README.md")
        self.git("add", "README-link.md")
        self.git("commit", "-m", "add symlink")
        output = self.base / "must-not-exist.zip"

        with self.assertRaisesRegex(ExportError, "tracked symlinks"):
            export_template(self.repo, output)
        self.assertFalse(output.exists())

    def test_tracked_personal_path_is_refused_by_snapshot_validation(self) -> None:
        private_path = "/" + "home" + "/" + "synthetic-owner" + "/workspace"
        marker = self.repo / "docs/private-marker.md"
        marker.write_text(private_path, encoding="utf-8")
        self.git("add", "docs/private-marker.md")
        self.git("commit", "-m", "add private marker")
        output = self.base / "must-not-exist.zip"

        with self.assertRaisesRegex(ExportError, "user-specific home path"):
            export_template(self.repo, output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
