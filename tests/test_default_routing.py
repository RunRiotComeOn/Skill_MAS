"""Run the shipped plugin bootstrap without a checkout or plugin environment."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]


class DefaultRoutingTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(
            (REPOSITORY / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.hooks = json.loads(
            (REPOSITORY / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )["hooks"]

    def skill_namespaces(self):
        """Resolve the actual skill names advertised by the plugin on disk."""
        namespaces = set()
        for skill in (REPOSITORY / "skills").glob("*/SKILL.md"):
            text = skill.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), str(skill))
            metadata = text.split("---", 2)[1]
            name = re.search(r"^name:\s*([^\n]+)$", metadata, re.MULTILINE)
            self.assertIsNotNone(name, str(skill))
            skill_name = name.group(1).strip().strip("\"'")
            namespaces.add("{}:{}".format(self.manifest["name"], skill_name))
        self.assertTrue(namespaces, "The bootstrap must have a packaged skill to load")
        return namespaces

    def test_marketplace_resolves_the_plugin_and_its_bootstrap(self):
        marketplace = json.loads(
            (REPOSITORY / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        entries = [
            entry for entry in marketplace["plugins"]
            if entry["name"] == self.manifest["name"]
        ]
        self.assertEqual(len(entries), 1)
        self.assertEqual((REPOSITORY / entries[0]["source"]).resolve(), REPOSITORY)
        # Custom component declarations can change which hook or skill is loaded.
        # This package deliberately uses Claude Code's standard locations.
        self.assertNotIn("hooks", self.manifest)
        self.assertNotIn("skills", self.manifest)
        self.assertNotIn("hooks", entries[0])
        self.assertNotIn("skills", entries[0])
        self.assertTrue(self.hooks.get("SessionStart"))
        self.skill_namespaces()

    def test_session_bootstrap_runs_in_isolation_for_all_session_sources(self):
        namespaces = self.skill_namespaces()
        environment = os.environ.copy()
        for name in list(environment):
            if name.startswith("CLAUDE_"):
                environment.pop(name)
        if os.name == "nt":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            self.assertIsNotNone(shell, "Windows hook smoke test requires PowerShell")
            shell_arguments = [shell, "-NoProfile", "-NonInteractive", "-Command"]
        else:
            shell_arguments = ["/bin/sh", "-c"]

        contexts = []
        for source in ("startup", "resume", "clear", "compact", "fork"):
            with self.subTest(source=source), tempfile.TemporaryDirectory(
                prefix="skill mas hook "
            ) as directory:
                event = json.dumps({
                    "session_id": "isolated-hook-test",
                    "cwd": directory,
                    "hook_event_name": "SessionStart",
                    "source": source,
                })
                outputs = []
                for group in self.hooks["SessionStart"]:
                    matcher = group.get("matcher", "")
                    if matcher not in ("", "*") and not re.search(matcher, source):
                        continue
                    for handler in group["hooks"]:
                        self.assertEqual(handler["type"], "command")
                        self.assertFalse(handler.get("async", False))
                        result = subprocess.run(
                            shell_arguments + [handler["command"]],
                            cwd=directory,
                            env=environment,
                            input=event,
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr, "")
                        output = result.stdout.strip()
                        self.assertTrue(output, "SessionStart must add routing context")
                        if output.startswith("{") and output.endswith("}"):
                            payload = json.loads(output)
                            self.assertNotEqual(payload.get("continue"), False)
                            self.assertNotEqual(payload.get("decision"), "block")
                            specific = payload["hookSpecificOutput"]
                            self.assertEqual(specific["hookEventName"], "SessionStart")
                            output = specific["additionalContext"]
                        outputs.append(output)

                context = "\n".join(outputs)
                self.assertTrue(context, "No bootstrap ran for {}".format(source))
                references = set(re.findall(r"\b[a-z0-9-]+:[a-z0-9-]+\b", context))
                self.assertTrue(references, "Context must identify a skill to load")
                self.assertTrue(references.issubset(namespaces), references - namespaces)
                self.assertEqual(list(Path(directory).iterdir()), [])
                contexts.append(context)
        self.assertEqual(len(set(contexts)), 1, "Default routing must survive resume and compaction")


if __name__ == "__main__":
    unittest.main()
