"""Exercise the installer CLI with isolated homes, projects, and checkouts."""

import os
import json
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
        self.write(self.source / "references" / "default-routing.md", "Use Skill-MAS automatically for relevant orchestration.\n")
        self.write(self.source / "assets" / "nested" / "notes.txt", "An additional portable asset\n")
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["USERPROFILE"] = str(self.home)
        self.env.pop("CLAUDE_CONFIG_DIR", None)
        self.env.pop("CODEX_HOME", None)
        self.codex = self.home / ".agents" / "skills" / "skill-mas"
        self.claude = self.home / ".claude" / "skills" / "skill-mas"
        self.codex_instructions = self.home / ".codex" / "AGENTS.md"
        self.claude_rule = self.home / ".claude" / "rules" / "skill-mas.md"

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
        for path, skill in ((self.codex_instructions, self.codex), (self.claude_rule, self.claude)):
            self.assertIn("Use Skill-MAS automatically", path.read_text())
            self.assertIn(json.dumps(str(skill / "SKILL.md")), path.read_text())
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
        self.assertEqual(result.stdout.count("Would write default routing"), 2)
        self.assertIn("Use Skill-MAS automatically", result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_identical_reinstall_does_not_modify_files_or_create_backups(self):
        self.run_installer("--agent", "both")
        files = list(self.codex.rglob("*")) + list(self.claude.rglob("*")) + [self.codex, self.claude, self.codex_instructions, self.claude_rule]
        previous = {path: (path.stat().st_mtime_ns, path.stat().st_ino) for path in files}
        result = self.run_installer("--agent", "both", "--force")
        self.assertIn("Already up to date", result.stdout)
        self.assertEqual(previous, {path: (path.stat().st_mtime_ns, path.stat().st_ino) for path in files})
        self.assertFalse((self.home / ".agents" / "skill-backups").exists())
        self.assertFalse((self.home / ".codex" / "skill-backups").exists())
        self.assertFalse((self.home / ".claude" / "skill-backups").exists())

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

    def test_codex_preserves_all_original_bytes_mode_and_full_backup(self):
        original = b"# Existing instructions\r\nKeep these rules.\r\nNo final newline"
        self.codex_instructions.parent.mkdir()
        self.codex_instructions.write_bytes(original)
        self.codex_instructions.chmod(0o640)
        self.run_installer("--agent", "codex")
        self.assertTrue(self.codex_instructions.read_bytes().endswith(original))
        self.assertEqual(self.codex_instructions.stat().st_mode & 0o777, 0o640)
        backups = list((self.home / ".codex" / "skill-backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.run_installer("--agent", "codex", "--no-default-routing")
        self.assertEqual(self.codex_instructions.read_bytes(), original)
        self.assert_installed(self.codex)

    def test_codex_updates_owned_block_preserving_both_surrounding_regions(self):
        original = b"Before\r\n<!-- SKILL-MAS:BEGIN -->\r\nOld policy\r\n<!-- SKILL-MAS:END -->\r\nAfter"
        self.codex_instructions.parent.mkdir()
        self.codex_instructions.write_bytes(original)
        self.run_installer("--agent", "codex")
        updated = self.codex_instructions.read_bytes()
        self.assertTrue(updated.startswith(b"Before\r\n<!-- SKILL-MAS:BEGIN -->"))
        self.assertTrue(updated.endswith(b"\nAfter"))
        self.assertNotIn(b"Old policy", updated)
        self.assertEqual(updated.count(b"<!-- SKILL-MAS:BEGIN -->"), 1)

    def test_nonempty_codex_override_receives_routing_and_normal_file_is_preserved(self):
        override = self.codex_instructions.with_name("AGENTS.override.md")
        self.write(override, "My overriding instructions")
        self.write(self.codex_instructions, "Normal instructions")
        self.run_installer("--agent", "codex")
        self.assertIn("Use Skill-MAS automatically", override.read_text())
        self.assertTrue(override.read_text().endswith("My overriding instructions"))
        self.assertEqual(self.codex_instructions.read_text(), "Normal instructions")

    def test_empty_override_is_not_populated(self):
        override = self.codex_instructions.with_name("AGENTS.override.md")
        self.write(override, "")
        self.run_installer("--agent", "codex")
        self.assertEqual(override.read_bytes(), b"")
        self.assertIn("Use Skill-MAS automatically", self.codex_instructions.read_text())

    def test_whitespace_only_override_is_not_populated(self):
        override = self.codex_instructions.with_name("AGENTS.override.md")
        self.write(override, " \n\t\n")
        self.run_installer("--agent", "codex")
        self.assertEqual(override.read_bytes(), b" \n\t\n")
        self.assertIn("Use Skill-MAS automatically", self.codex_instructions.read_text())

    def test_stale_normal_block_is_removed_when_override_takes_precedence(self):
        self.run_installer("--agent", "codex")
        override = self.codex_instructions.with_name("AGENTS.override.md")
        self.write(override, "Override instructions\n")
        self.run_installer("--agent", "codex")
        self.assertEqual(self.codex_instructions.read_bytes(), b"")
        self.assertIn("Use Skill-MAS automatically", override.read_text())
        self.run_installer("--agent", "codex", "--no-default-routing")
        self.assertEqual(override.read_text(), "Override instructions\n")

    def test_custom_codex_home_affects_instructions_only(self):
        config = self.root / "custom codex config"
        self.env["CODEX_HOME"] = str(config)
        self.run_installer("--agent", "codex")
        self.assert_installed(self.codex)
        self.assertIn(json.dumps(str(self.codex / "SKILL.md")), (config / "AGENTS.md").read_text())
        self.assertFalse(self.codex_instructions.exists())
        self.run_installer("--agent", "codex", "--scope", "project")
        self.assertIn("Use Skill-MAS automatically", (self.project / "AGENTS.md").read_text())

    def test_custom_claude_config_receives_rule_without_changing_claude_md(self):
        config = self.root / "custom claude config"
        self.env["CLAUDE_CONFIG_DIR"] = str(config)
        self.write(config / "CLAUDE.md", "User instructions")
        self.run_installer("--agent", "claude")
        self.assertIn(json.dumps(str(config / "skills" / "skill-mas" / "SKILL.md")),
                      (config / "rules" / "skill-mas.md").read_text())
        self.assertEqual((config / "CLAUDE.md").read_text(), "User instructions")

    def test_project_routing_uses_shareable_relative_paths_and_existing_override(self):
        self.write(self.project / "AGENTS.override.md", "Project override")
        self.write(self.project / "CLAUDE.md", "Project instructions")
        self.run_installer("--agent", "both", "--scope", "project")
        codex = (self.project / "AGENTS.override.md").read_text()
        claude = (self.project / ".claude" / "rules" / "skill-mas.md").read_text()
        self.assertIn('".agents/skills/skill-mas/SKILL.md"', codex)
        self.assertIn('".claude/skills/skill-mas/SKILL.md"', claude)
        self.assertNotIn(str(self.project), codex + claude)
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertEqual((self.project / "CLAUDE.md").read_text(), "Project instructions")

    def test_paths_with_quotes_and_newlines_are_json_encoded(self):
        config = self.root / 'claude `config` "with quotes"\nand newline'
        self.env["CLAUDE_CONFIG_DIR"] = str(config)
        self.run_installer("--agent", "claude")
        rule = (config / "rules" / "skill-mas.md").read_text()
        encoded = next(line.strip() for line in rule.splitlines() if line.startswith("    "))
        self.assertEqual(json.loads(encoded), str(config / "skills" / "skill-mas" / "SKILL.md"))

    def test_no_default_routing_on_fresh_install_leaves_instructions_unwritten(self):
        self.run_installer("--agent", "both", "--no-default-routing")
        self.assert_installed(self.codex)
        self.assert_installed(self.claude)
        self.assertFalse(self.codex_instructions.parent.exists())
        self.assertFalse(self.claude_rule.parent.exists())

    def test_no_default_routing_removes_owned_claude_rule_and_is_idempotent(self):
        self.run_installer("--agent", "both")
        original = self.claude_rule.read_bytes()
        self.run_installer("--agent", "both", "--no-default-routing")
        self.assertFalse(self.claude_rule.exists())
        self.assertEqual(self.codex_instructions.read_bytes(), b"")
        backups = list((self.home / ".claude" / "skill-backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.run_installer("--agent", "both", "--no-default-routing")
        self.assertEqual(list((self.home / ".claude" / "skill-backups").iterdir()), backups)

    def test_no_default_routing_preserves_unrelated_claude_rule_content(self):
        self.run_installer("--agent", "claude")
        self.claude_rule.write_bytes(self.claude_rule.read_bytes() + b"My additional instructions")
        self.run_installer("--agent", "claude", "--no-default-routing")
        self.assertEqual(self.claude_rule.read_bytes(), b"My additional instructions")
        self.run_installer("--agent", "claude", "--no-default-routing")
        self.assertEqual(self.claude_rule.read_bytes(), b"My additional instructions")

    def test_no_default_routing_cleans_both_codex_instruction_candidates(self):
        self.run_installer("--agent", "codex")
        override = self.codex_instructions.with_name("AGENTS.override.md")
        self.write(override, self.codex_instructions.read_text() + "Keep override")
        self.run_installer("--agent", "codex", "--no-default-routing")
        self.assertEqual(self.codex_instructions.read_bytes(), b"")
        self.assertEqual(override.read_text(), "Keep override")

    def test_unmanaged_claude_rule_conflict_prevents_all_writes(self):
        self.write(self.claude_rule, "Unrelated policy\n")
        result = self.run_installer("--agent", "both", expected=1)
        self.assertIn("--force", result.stderr)
        self.assertFalse(self.codex.exists())
        self.assertFalse(self.claude.exists())
        self.assertFalse(self.codex_instructions.exists())
        self.assertEqual(self.claude_rule.read_text(), "Unrelated policy\n")

    def test_force_replaces_unmanaged_claude_rule_with_complete_backup(self):
        self.write(self.claude_rule, "Unrelated policy\n")
        self.run_installer("--agent", "claude", "--force")
        self.assertIn("Use Skill-MAS automatically", self.claude_rule.read_text())
        backups = list((self.home / ".claude" / "skill-backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "Unrelated policy\n")

    def test_malformed_markers_are_rejected_even_with_force_before_any_writes(self):
        malformed = (
            "<!-- SKILL-MAS:BEGIN -->\nNo end",
            "<!-- SKILL-MAS:END -->\n<!-- SKILL-MAS:BEGIN -->\n",
            "<!-- SKILL-MAS:BEGIN -->\n<!-- SKILL-MAS:END -->\n" * 2,
            "prefix <!-- SKILL-MAS:BEGIN -->\n<!-- SKILL-MAS:END -->\n",
            "<!-- SKILL-MAS:BROKEN -->\n",
        )
        for contents in malformed:
            with self.subTest(contents=contents):
                self.write(self.claude_rule, contents)
                result = self.run_installer("--agent", "both", "--force", expected=1)
                self.assertIn("markers", result.stderr)
                self.assertFalse(self.codex.exists())
                self.assertFalse(self.claude.exists())
                self.assertEqual(self.claude_rule.read_text(), contents)

    def test_instruction_symlinks_are_rejected_even_when_disabling_routing(self):
        for path in (self.codex_instructions, self.codex_instructions.with_name("AGENTS.override.md"), self.claude_rule):
            with self.subTest(path=path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(self.project / "untouched.md")
                self.run_installer("--agent", "both", "--force", "--no-default-routing", expected=1)
                self.assertFalse(self.codex.exists())
                self.assertFalse(self.claude.exists())
                self.assertFalse((self.project / "untouched.md").exists())
                path.unlink()

    def test_routing_directory_symlink_is_rejected_before_skill_install(self):
        self.claude_rule.parent.parent.mkdir()
        self.claude_rule.parent.symlink_to(self.project, target_is_directory=True)
        self.run_installer("--agent", "both", "--force", expected=1)
        self.assertFalse(self.codex.exists())
        self.assertFalse(self.claude.exists())
        self.assertEqual(list(self.project.iterdir()), [])

    def test_directory_at_instruction_file_path_prevents_all_writes(self):
        self.claude_rule.mkdir(parents=True)
        self.run_installer("--agent", "both", "--force", expected=1)
        self.assertFalse(self.codex.exists())
        self.assertFalse(self.claude.exists())
        self.assertTrue(self.claude_rule.is_dir())

    def test_custom_codex_config_symlink_is_rejected(self):
        config = self.root / "linked config"
        config.symlink_to(self.project, target_is_directory=True)
        self.env["CODEX_HOME"] = str(config)
        self.run_installer("--agent", "codex", expected=1)
        self.assertFalse(self.codex.exists())
        self.assertEqual(list(self.project.iterdir()), [])

    def test_routing_backup_symlink_prevents_all_changes(self):
        self.write(self.codex_instructions, "Original\n")
        (self.codex_instructions.parent / "skill-backups").symlink_to(self.project, target_is_directory=True)
        self.run_installer("--agent", "both", "--force", expected=1)
        self.assertFalse(self.codex.exists())
        self.assertFalse(self.claude.exists())
        self.assertEqual(self.codex_instructions.read_text(), "Original\n")

    def test_dry_run_of_routing_update_and_removal_preserves_all_files(self):
        self.run_installer("--agent", "both")
        files = [path for path in self.home.rglob("*") if path.is_file()]
        previous = {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino) for path in files}
        result = self.run_installer("--agent", "both", "--no-default-routing", "--dry-run")
        self.assertIn("Would remove default routing", result.stdout)
        self.assertIn("Would back up", result.stdout)
        self.assertEqual(previous, {path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino) for path in files})
        self.assertFalse((self.home / ".codex" / "skill-backups").exists())
        self.assertFalse((self.home / ".claude" / "skill-backups").exists())

    def test_dry_run_previews_only_managed_routing_without_unrelated_instructions(self):
        self.write(self.codex_instructions, "Private instructions not relevant to the preview\n")
        result = self.run_installer("--agent", "codex", "--dry-run")
        self.assertIn("Use Skill-MAS automatically", result.stdout)
        self.assertNotIn("Private instructions", result.stdout)
        self.assertEqual(self.codex_instructions.read_text(), "Private instructions not relevant to the preview\n")
        self.assertFalse(self.codex.exists())

    def test_missing_and_invalid_routing_source_prevent_all_writes(self):
        policy = self.source / "references" / "default-routing.md"
        policy.unlink()
        self.run_installer("--agent", "both", expected=1)
        self.assertEqual(list(self.home.iterdir()), [])
        for contents in (b"\xff", b"<!-- SKILL-MAS:BEGIN -->\n", b" \n"):
            with self.subTest(contents=contents):
                policy.write_bytes(contents)
                self.run_installer("--agent", "both", expected=1)
                self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
