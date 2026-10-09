# Skill-MAS in Codex and Claude Code

The installable package is [`skills/skill-mas/`](../skills/skill-mas/). It contains
one `SKILL.md` entry point and four reference profiles. Execution uses the host's
existing tools, model access, and permissions. The main agent decomposes the
task, assigns roles, checks results, and returns the requested deliverable.

## Install from a clone

From the repository root, run the standard-library-only installer with Python
3.9 or later. No `pip install` is required.

```bash
python3 scripts/install_agent_skill.py --agent codex
python3 scripts/install_agent_skill.py --agent claude
# Or install for both in one command:
python3 scripts/install_agent_skill.py --agent both
```

| Agent | User scope (default) | Project scope |
| --- | --- | --- |
| Codex | `~/.agents/skills/skill-mas/` | `<project>/.agents/skills/skill-mas/` |
| Claude Code | `~/.claude/skills/skill-mas/` | `<project>/.claude/skills/skill-mas/` |

For Claude's user scope, an explicit `CLAUDE_CONFIG_DIR` replaces `~/.claude`.
The installer copies files, so the installed skill does not depend on keeping
the clone. Project scope makes the skill available in that project; commit the
installed directory in your own project to share it with teammates.

```bash
python3 scripts/install_agent_skill.py --agent both --scope project --project /path/to/project
python3 scripts/install_agent_skill.py --agent both --dry-run
```

Omitting `--project` in project scope uses the current working directory. Use an
explicit path when running from the Skill_MAS clone to install into another repo.
On Windows, use `python` instead of `python3` if that is your Python command.

For manual installation, copy the **entire** `skills/skill-mas` directory to the
appropriate skills directory above. Copying only `SKILL.md` omits the profiles.

## Claude Code plugin

The repository also serves as a small plugin marketplace. In Claude Code:

```text
/plugin marketplace add linhh29/Skill_MAS
/plugin install skill-mas@skill-mas-marketplace
```

Complete the install in the plugin interface. The plugin discovers the same
`skills/skill-mas/` directory and exposes `/skill-mas:skill-mas`. Use this route
or the copy installer for Claude, rather than both. To try the plugin from a
local clone without registering a marketplace:

```bash
claude --plugin-dir /absolute/path/to/Skill_MAS
```

## Invoke and select a profile

Start a new session in your working project after installation. In Codex, choose
the skill from `/skills` or mention `$skill-mas`. In Claude Code, invoke
`/skill-mas` for a copied skill or `/skill-mas:skill-mas` for a plugin install.
You can also describe a task for automatic skill selection.

```text
$skill-mas profile=drb Research the trade-offs among these three system designs, verify sources, and write a comparison.
/skill-mas profile=hlemath Solve [problem], check small cases independently, and explain the proof.
/skill-mas:skill-mas profile=bcp Identify [entity] from these clues, with evidence for each match.
$skill-mas profile=vitabench Compare the available options against my constraints, then carry out the authorized steps and verify the results.
```

`profile=...` is an instruction in the prompt, not a CLI flag. If omitted, the
main agent selects a suitable profile. Each profile is read only when relevant.
For software work you can simply ask:

```text
$skill-mas Implement [feature]. Delegate independent components with clear file ownership, then integrate and test the result.
```

Subagent availability depends on the host version and session configuration.
This package neither enables experimental agent teams nor changes concurrency
limits. If delegation is unavailable, the main agent executes the roles
sequentially and reports that limitation. Search and transactional tools likewise
need to be available in the user's session. Installing this skill does not change
`AGENTS.md`, `CLAUDE.md`, model configuration, or permissions.

## How the optimized skills were adapted

The original [`optimized_skill/*.md`](../optimized_skill/) files remain unchanged
and are still used by the research pipeline. The installed profiles are manual,
portable adaptations of the source snapshots at commit `b55d47e`; each profile
links to its original. They run inside the host agent rather than generating and
executing a standalone Python MAS by default.

| Source | Installed reference | Preserved orchestration patterns |
| --- | --- | --- |
| [`drb.md`](../optimized_skill/drb.md) | [`drb.md`](../skills/skill-mas/references/drb.md) | Shared scope, bounded parallel branches, output contracts, compact memory, coverage check, synthesis |
| [`hlemath.md`](../optimized_skill/hlemath.md) | [`hlemath.md`](../skills/skill-mas/references/hlemath.md) | Interpretation register, independent verification, small-case calibration, recovery, final-format check |
| [`bcp.md`](../optimized_skill/bcp.md) | [`bcp.md`](../skills/skill-mas/references/bcp.md) | Constraint weighting, multiple hypotheses, adaptive retrieval, link verification, active merge |
| [`vitabench.md`](../optimized_skill/vitabench.md) | [`vitabench.md`](../skills/skill-mas/references/vitabench.md) | Constraint matrix, acquisition/selection/action separation, structured decisions, reality checks, completion verification |

The adaptation replaces benchmark-specific token floors and length thresholds
with task-sized budgets and evidence checks. Unknown facts remain unknown;
answer delimiters and benchmark sentinel strings are used only when requested.
State-changing actions retain the host's authorization requirements and are not
retried blindly. Each profile documents its adjustments. Benchmark scores have
not been validated for this host-native adaptation.

When updating a source skill, review its corresponding portable profile and
update the pinned source link after adapting the changes. There is no automatic
overwrite from raw benchmark instructions into the installed skill.

## Update and remove

For a copied installation, update your clone and run the installer again:

```bash
git pull --ff-only
python3 scripts/install_agent_skill.py --agent both --force
```

Use the same scope and project arguments as the original install. Identical
installs are left alone. A differing destination is refused unless `--force` is
given; forced updates preserve the previous installation under the corresponding
configuration directory's `skill-backups/` and print its location. Backups live
outside `skills/`, so they are not discovered as duplicate skills. Symlink
destinations are refused; manage an existing symlink installation separately.

To remove a copied install, delete only its `skill-mas` directory from the
installation path shown above. To restore a backup, move it back to that exact
path after removing the replacement. Restart the agent if its skill list is stale.

For a plugin installation, use Claude Code's `/plugin` interface to update or
uninstall `skill-mas`; do not manage the plugin cache with the copy installer.

## Troubleshooting

- **Skill missing:** check the scope, target project, and the presence of both
  `SKILL.md` and `references/` in the destination, then restart the agent.
- **Two entries:** remove either the copied Claude skill or the plugin install.
  Also check for an older project-scoped copy shadowing a user installation.
- **No parallel execution:** ensure the session provides native subagent tools.
  The skill cannot add a missing tool; the sequential fallback remains usable.
- **Missing tools:** enable them through your normal host setup or provide source
  material. Installation does not configure retrieval indexes or API credentials.
- **Destination conflict:** inspect the existing skill before using `--force`.
  Use `--dry-run` to preview paths and `--help` for available options.

## Packaging references

The layout follows the shared `SKILL.md` convention documented by
[Codex](https://learn.chatgpt.com/docs/build-skills) and
[Claude Code](https://code.claude.com/docs/en/skills). The Claude marketplace
entry follows the root-source pattern in
[anthropics/skills](https://github.com/anthropics/skills/blob/main/.claude-plugin/marketplace.json);
the shared skills directory with a platform manifest is also used by
[obra/superpowers](https://github.com/obra/superpowers).
See the official [plugin](https://code.claude.com/docs/en/plugins) and
[marketplace](https://code.claude.com/docs/en/plugin-marketplaces) documentation
for host-specific management details.
