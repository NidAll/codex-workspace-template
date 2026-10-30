from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_template import ROOT, SKIP_DIRS, validate


class ValidateTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.copy = Path(self.temp.name) / "copied template"
        shutil.copytree(ROOT, self.copy, ignore=shutil.ignore_patterns(*SKIP_DIRS))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_template_copy_validates_from_explicit_root(self) -> None:
        self.assertEqual(validate(self.copy), [])

    def test_cli_validates_copy_path_with_spaces(self) -> None:
        script = ROOT / "scripts/validate_template.py"
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(self.copy)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Template validation passed", result.stdout)

    def test_instruction_budget_violation_is_reported(self) -> None:
        guide = self.copy / "AGENTS.md"
        guide.write_text(guide.read_text(encoding="utf-8") + "x" * 7000, encoding="utf-8")
        errors = validate(self.copy)
        self.assertTrue(any("AGENTS.md is" in error and "limit" in error for error in errors), errors)

    def test_model_defaults_and_positive_limits_can_be_customized(self) -> None:
        config = self.copy / ".codex/config.toml"
        contents = config.read_text(encoding="utf-8")
        contents = contents.replace('"gpt-6.1-sol"', '"custom-main-model"')
        contents = contents.replace('"xhigh"', '"medium"')
        contents = contents.replace("max_concurrent_threads_per_session = 3", "max_concurrent_threads_per_session = 2")
        contents = contents.replace("max_depth = 1", "max_depth = 2")
        contents = contents.replace('"gpt-6-luna"', '"custom-agent-model"')
        contents = contents.replace('default_subagent_reasoning_effort = "high"', 'default_subagent_reasoning_effort = "low"')
        config.write_text(contents, encoding="utf-8")

        for role in ("explorer", "researcher", "worker"):
            agent = self.copy / f".codex/agents/{role}.toml"
            contents = agent.read_text(encoding="utf-8")
            contents = contents.replace('model = "gpt-6-luna"', 'model = "custom-agent-model"')
            contents = contents.replace('model_reasoning_effort = "high"', 'model_reasoning_effort = "medium"')
            contents = contents.replace('model_reasoning_effort = "max"', 'model_reasoning_effort = "ultra"')
            agent.write_text(contents, encoding="utf-8")

        self.assertEqual(validate(self.copy), [])

    def test_array_reasoning_effort_is_reported_without_crashing(self) -> None:
        config = self.copy / ".codex/config.toml"
        contents = config.read_text(encoding="utf-8")
        contents = contents.replace('model_reasoning_effort = "xhigh"', "model_reasoning_effort = []", 1)
        config.write_text(contents, encoding="utf-8")

        errors = validate(self.copy)
        self.assertTrue(any("model_reasoning_effort must use" in error for error in errors), errors)

    def test_escaping_relative_map_link_is_reported(self) -> None:
        readme = self.copy / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n[escape](../../outside.md)\n", encoding="utf-8")
        errors = validate(self.copy)
        self.assertTrue(any("escapes template root" in error for error in errors), errors)

    def test_broken_link_in_nested_markdown_is_reported(self) -> None:
        guide = self.copy / "docs/nested/guide.md"
        guide.parent.mkdir(parents=True)
        guide.write_text("[missing](not-here.md)\n", encoding="utf-8")
        errors = validate(self.copy)
        self.assertTrue(any("docs/nested/guide.md" in error and "missing local link" in error for error in errors), errors)

    def test_personal_home_paths_and_literal_email_are_reported(self) -> None:
        unix_path = "/" + "home" + "/" + "synthetic-owner" + "/" + "workspace"
        tilde_path = "~" + "synthetic-owner" + "/workspace"
        slash = chr(92)
        windows_path = "C:" + slash + "Users" + slash + "synthetic-owner" + slash + "workspace"
        address = "synthetic-owner" + "@mail.invalid"
        marker = self.copy / "docs/privacy-probe.md"
        marker.write_text("\n".join((unix_path, tilde_path, windows_path, address)), encoding="utf-8")

        errors = validate(self.copy)
        self.assertTrue(any("user-specific home path" in error for error in errors), errors)
        self.assertTrue(any("literal email address" in error for error in errors), errors)

    def test_generic_windows_home_environment_variable_is_allowed(self) -> None:
        marker = self.copy / "docs/environment-path.md"
        marker.write_text("Use %USERPROFILE% as the current user's directory.\n", encoding="utf-8")
        errors = validate(self.copy)
        self.assertFalse(any("user-specific home path" in error for error in errors), errors)

    def test_neutral_example_email_domains_are_allowed(self) -> None:
        marker = self.copy / "docs/neutral-contact.md"
        marker.write_text("test@example.com test@example.invalid\n", encoding="utf-8")
        errors = validate(self.copy)
        self.assertFalse(any("literal email address" in error for error in errors), errors)

    def test_credential_assignment_is_reported(self) -> None:
        key = "API" + "_KEY"
        secret_payload = "synthetic-" + "credential-value-123456"
        marker = self.copy / "docs/credential-probe.md"
        marker.write_text(key + "=" + secret_payload + "\n", encoding="utf-8")
        errors = validate(self.copy)
        self.assertTrue(any("appears to contain a credential" in error for error in errors), errors)

    def test_runtime_private_artifacts_are_reported_but_caches_are_skipped(self) -> None:
        (self.copy / ".codex/tasks").mkdir(parents=True)
        (self.copy / ".codex/tasks/local.md").write_text("private task", encoding="utf-8")
        (self.copy / ".codex/auth.json").write_text("{}", encoding="utf-8")
        (self.copy / ".env").write_text("MODE=release\n", encoding="utf-8")
        (self.copy / "data/sessions").mkdir(parents=True)
        (self.copy / "data/sessions/session.jsonl").write_text("{}\n", encoding="utf-8")
        (self.copy / "data/session.sqlite3").write_bytes(b"sqlite")
        (self.copy / "models").mkdir()
        (self.copy / "models/checkpoint.safetensors").write_bytes(b"weights")
        cache = self.copy / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "private.md").write_text("/" + "home" + "/synthetic-owner", encoding="utf-8")

        errors = validate(self.copy)
        for marker in (".codex/tasks", "auth.json", ".env", "session.jsonl", "session.sqlite3", "checkpoint.safetensors"):
            self.assertTrue(any(marker in error for error in errors), errors)
        self.assertFalse(any("__pycache__" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
