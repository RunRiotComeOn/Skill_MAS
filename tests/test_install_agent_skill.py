"""Exercise the installer CLI with isolated homes, projects, and checkouts."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install_agent_skill.py"


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="skill mas tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.home = self.root / "test home"
        self.project = self.root / "example project"
        self.repository = self.root / "source checkout"
        self.source = self.repository / "skills" / "skill-mas"
        self.script = self.repository / "scripts" / "install_agent_skill.py"
        self.home.mkdir()
        self.project.mkdir()
        self.script.parent.mkdir(parents=True)
        self.source.mkdir(parents=True)
        shutil.copy2(INSTALLER, self.script)
        self.write(self.source / "SKILL.md", "---\nname: skill-mas\ndescription: Orchestrate agents\n---\nSkill instructions\n")
        for name in ("drb", "hlemath", "bcp", "vitabench"):
            self.write(self.source / "references" / (name + ".md"), "# {}\nProfile instructions\n".format(name))
        self.write(self.source / "assets" / "nested" / "notes.txt", "An additional portable asset\n")
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env.pop("CLAUDE_CONFIG_DIR", None)
        self.codex = self.home / ".agents" / "skills" / "skill-mas"
        self.claude = self.home / ".claude" / "skills" / "skill-mas"

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run_installer(self, *arguments, expected=0):
        result = subprocess.run([sys.executable, str(self.script), *arguments], cwd=str(self.project), env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def assert_installed(self, destination):
        expected = {path.relative_to(self.source): path.read_bytes() for path in self.source.rglob("*") if path.is_file()}
        actual = {path.relative_to(destination): path.read_bytes() for path in destination.rglob("*") if path.is_file()}
        self.assertEqual(expected, actual)
        self.assertFalse(any(path.is_symlink() for path in destination.rglob("*")))

    def test_both_user_installs_are_complete_independent_copies(self):
        self.run_installer("--agent", "both")
        self.assert_installed(self.codex)
        self.assert_installed(self.claude)
        shutil.rmtree(self.repository)
        self.assertTrue((self.codex / "references" / "drb.md").is_file())
        self.assertTrue((self.claude / "assets" / "nested" / "notes.txt").is_file())

    def test_agent_selection_does_not_install_other_agent(self):
        self.run_installer("--agent", "codex")
        self.assert_installed(self.codex)
        self.assertFalse(self.claude.exists())

    def test_project_scope_defaults_to_current_directory(self):
        self.run_installer("--agent", "both", "--scope", "project")
        self.assert_installed(self.project / ".agents" / "skills" / "skill-mas")
        self.assert_installed(self.project / ".claude" / "skills" / "skill-mas")
        self.assertFalse(self.codex.exists())
        self.assertFalse(self.claude.exists())

    def test_explicit_project_path_with_spaces(self):
        project = self.root / "another project"
        project.mkdir()
        self.run_installer("--agent", "claude", "--scope", "project", "--project", str(project))
        self.assert_installed(project / ".claude" / "skills" / "skill-mas")
        self.assertFalse((self.project / ".claude").exists())

    def test_custom_claude_config_directory_applies_only_to_user_scope(self):
        config = self.root / "custom claude config"
        self.env["CLAUDE_CONFIG_DIR"] = str(config)
        self.run_installer("--agent", "claude")
        self.assert_installed(config / "skills" / "skill-mas")
        self.assertFalse(self.claude.exists())
        self.run_installer("--agent", "claude", "--scope", "project")
        self.assert_installed(self.project / ".claude" / "skills" / "skill-mas")

    def test_dry_run_creates_no_directories(self):
        result = self.run_installer("--agent", "both", "--dry-run")
        self.assertEqual(result.stdout.count("Would install"), 2)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_identical_reinstall_does_not_modify_files_or_create_backups(self):
        self.run_installer("--agent", "codex")
        files = list(self.codex.rglob("*")) + [self.codex]
        previous = {path: (path.stat().st_mtime_ns, path.stat().st_ino) for path in files}
        result = self.run_installer("--agent", "codex", "--force")
        self.assertIn("Already up to date", result.stdout)
        self.assertEqual(previous, {path: (path.stat().st_mtime_ns, path.stat().st_ino) for path in files})
        self.assertFalse((self.home / ".agents" / "skill-backups").exists())

    def test_conflict_in_second_target_leaves_first_target_unwritten(self):
        self.write(self.claude / "SKILL.md", "Local customization\n")
        result = self.run_installer("--agent", "both", expected=1)
        self.assertIn("--force", result.stderr)
        self.assertFalse((self.home / ".agents").exists())
        self.assertEqual((self.claude / "SKILL.md").read_text(), "Local customization\n")

    def test_force_preserves_complete_previous_tree_outside_skills(self):
        self.write(self.codex / "SKILL.md", "Customized\n")
        self.write(self.codex / "local" / "notes.txt", "Keep me\n")
        (self.codex / "empty directory").mkdir()
        result = self.run_installer("--agent", "codex", "--force")
        self.assert_installed(self.codex)
        backups = list((self.home / ".agents" / "skill-backups").iterdir())
        self.assertEqual(len(backups), 1)
        backup = backups[0]
        self.assertIn(str(backup), result.stdout)
        self.assertEqual((backup / "SKILL.md").read_text(), "Customized\n")
        self.assertEqual((backup / "local" / "notes.txt").read_text(), "Keep me\n")
        self.assertTrue((backup / "empty directory").is_dir())
        self.assertEqual(list(self.codex.parent.iterdir()), [self.codex])

    def test_force_dry_run_preserves_existing_installation(self):
        self.write(self.codex / "SKILL.md", "Customized\n")
        result = self.run_installer("--agent", "codex", "--force", "--dry-run")
        self.assertIn("Would back up", result.stdout)
        self.assertEqual((self.codex / "SKILL.md").read_text(), "Customized\n")
        self.assertFalse((self.home / ".agents" / "skill-backups").exists())

    def test_incomplete_source_does_not_create_destination(self):
        (self.source / "references" / "bcp.md").unlink()
        result = self.run_installer("--agent", "both", expected=1)
        self.assertIn("references/bcp.md", result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_symlink_in_source_is_rejected(self):
        (self.source / "linked").symlink_to(self.project, target_is_directory=True)
        result = self.run_installer("--agent", "codex", expected=1)
        self.assertIn("symbolic link", result.stderr)
        self.assertFalse(self.codex.exists())

    def test_destination_symlink_is_rejected_even_with_force(self):
        self.codex.parent.mkdir(parents=True)
        self.codex.symlink_to(self.project, target_is_directory=True)
        result = self.run_installer("--agent", "codex", "--force", expected=1)
        self.assertIn("symbolic link", result.stderr)
        self.assertTrue(self.codex.is_symlink())
        self.assertEqual(list(self.project.iterdir()), [])

    def test_destination_ancestor_symlink_is_rejected(self):
        (self.home / ".agents").symlink_to(self.project, target_is_directory=True)
        self.run_installer("--agent", "codex", expected=1)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_symlink_inside_existing_destination_is_rejected(self):
        self.write(self.codex / "SKILL.md", "Custom\n")
        (self.codex / "linked").symlink_to(self.project, target_is_directory=True)
        self.run_installer("--agent", "codex", "--force", expected=1)
        self.assertEqual((self.codex / "SKILL.md").read_text(), "Custom\n")

    def test_regular_file_at_destination_is_never_overwritten(self):
        self.write(self.codex, "Unrelated file\n")
        self.run_installer("--agent", "codex", "--force", expected=1)
        self.assertEqual(self.codex.read_text(), "Unrelated file\n")

    def test_source_destination_overlap_is_rejected(self):
        self.env["CLAUDE_CONFIG_DIR"] = str(self.repository)
        result = self.run_installer("--agent", "claude", "--force", expected=1)
        self.assertIn("overlap", result.stderr)
        self.assertTrue((self.source / "SKILL.md").is_file())

    def test_duplicate_agent_destinations_are_rejected_before_writing(self):
        self.env["CLAUDE_CONFIG_DIR"] = str(self.home / ".agents")
        result = self.run_installer("--agent", "both", expected=1)
        self.assertIn("overlap", result.stderr)
        self.assertFalse(self.codex.exists())

    def test_backup_directory_symlink_is_rejected(self):
        self.write(self.codex / "SKILL.md", "Custom\n")
        (self.home / ".agents" / "skill-backups").symlink_to(self.project, target_is_directory=True)
        self.run_installer("--agent", "codex", "--force", expected=1)
        self.assertEqual((self.codex / "SKILL.md").read_text(), "Custom\n")

    def test_invalid_project_and_invalid_arguments_report_clean_errors(self):
        self.run_installer("--agent", "codex", "--scope", "project", "--project", str(self.root / "missing"), expected=1)
        self.run_installer("--agent", "codex", "--project", str(self.project), expected=2)
        self.run_installer(expected=2)


if __name__ == "__main__":
    unittest.main()
