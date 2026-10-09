# Skill-MAS in Codex and Claude Code

The installable package is [`skills/skill-mas/`](../skills/skill-mas/). It contains
one `SKILL.md` entry point, four task profiles, and default routing guidance.
After installation, the main agent automatically selects the appropriate
optimized skill for the current task, combines it with relevant existing skills,
and coordinates execution and verification.
Execution uses the host's existing tools, model access, and permissions.

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
installed directory and startup instructions in your own project to share them
with teammates.

```bash
python3 scripts/install_agent_skill.py --agent both --scope project --project /path/to/project
python3 scripts/install_agent_skill.py --agent both --dry-run
```

Omitting `--project` in project scope uses the current working directory. Use an
explicit path when running from the Skill_MAS clone to install into another repo.
On Windows, use `python` instead of `python3` if that is your Python command.

Manual copying of the **entire** `skills/skill-mas` directory supports ordinary
host skill discovery, but does not install the default startup rules. Use the
installer or Claude plugin for the default-on experience.

## Default startup routing

The installer enables routing by default, in addition to copying the skill:

| Host | User scope | Project scope |
| --- | --- | --- |
| Codex | Managed block in `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`) | Managed block in `<project>/AGENTS.md` |
| Claude Code | `~/.claude/rules/skill-mas.md`, honoring `CLAUDE_CONFIG_DIR` | `<project>/.claude/rules/skill-mas.md` |

Codex's existing nonempty `AGENTS.override.md` takes priority; if present, the
installer updates that active file instead of creating an override. The managed
block is delimited by `<!-- SKILL-MAS:BEGIN -->` and `<!-- SKILL-MAS:END -->`.
Content outside that block is preserved. Changed instruction files are backed up,
and repeating an identical install does not add duplicate blocks. Claude's
dedicated rule has no path restriction, so the host loads it at session startup.

The startup context tells the main agent to consult Skill-MAS for substantive
tasks, select relevant profiles internally, and compose with installed skills.
Codex also explicitly allows implicit invocation in `agents/openai.yaml`; Claude
uses its normal model-invocable skill behavior. These are model instructions,
not a guarantee that every prompt starts subagents. Simple tasks stay direct.
Host settings, instruction precedence, and context limits still apply.

To install only the skill without this default startup routing, or remove the
managed routing from a previous installation:

```bash
python3 scripts/install_agent_skill.py --agent both --no-default-routing --force
```

Use the same scope/project as before. This returns to normal host skill discovery;
the skill may still be selected when relevant or invoked explicitly. You can also
ask the agent to skip Skill-MAS or delegation for an individual task. To remove
the skill completely, follow [Update and remove](#update-and-remove).

## Claude Code plugin

The repository also serves as a small plugin marketplace. In Claude Code:

```text
/plugin marketplace add linhh29/Skill_MAS
/plugin install skill-mas@skill-mas-marketplace
```

Complete the install in the plugin interface and start a new session. From
version 1.1.0, `hooks/hooks.json` injects default routing on `SessionStart`, including
resume, clear, and compaction. The hook emits a fixed instruction through the
shell's `echo`; it performs no network requests, configuration writes, or model
calls. The same `skills/skill-mas/` package is loaded automatically as needed.
Use this route or the copy installer for Claude, rather than both.

To try the plugin from a local clone without registering a marketplace:

```bash
claude --plugin-dir /absolute/path/to/Skill_MAS
```

## Everyday use and skill composition

Start a new session in your working project after installation, then ask normally:

```text
Research the trade-offs among these three system designs and write a comparison.
Solve [problem] and explain the proof.
Identify the entity matching these clues, with evidence for each match.
Compare the options against my constraints and carry out the authorized steps.
Implement [feature], integrate the changes, and test the result.
```

The main agent chooses `drb`, `hlemath`, `bcp`, or `vitabench` by task shape. For
general software work it uses the base workflow and applicable coding skills.
Mixed tasks can use different profiles for different branches, without loading
all profiles up front. Delegation is chosen according to the task and available tools.

Skill-MAS supplies decomposition, handoff contracts, and verification; existing
domain skills provide their specialist procedures. If another orchestration
skill already owns planning and scheduling, keep that single workflow and add
only complementary Skill-MAS checks. Do not create competing plans, duplicate
teams, or recursive whole-task delegation. User-selected workflows take priority.

Explicit invocation remains available for debugging or a deliberate override:

```text
$skill-mas profile=drb Compare these designs.
/skill-mas profile=hlemath Solve this problem and explain the proof.
/skill-mas:skill-mas profile=bcp Find the entity matching these clues.
```

These are optional Codex, copied-Claude, and plugin-Claude forms respectively.
`profile=...` is a prompt instruction, not a CLI flag.

Subagent availability depends on the host version and session configuration.
This package neither enables experimental agent teams nor changes concurrency
limits. If delegation is unavailable, the main agent executes the roles
sequentially and reports that limitation. Search and transactional tools likewise
need to be available in the user's session. The installer modifies only its skill
and routing files; it does not alter `CLAUDE.md`, model settings, or permissions.
The plugin uses session context rather than modifying user instruction files.

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

To remove a copied install, first run the installer with `--no-default-routing`
and the same agent/scope/project options (plus `--force` if the package differs).
Then delete only the installed `skill-mas` directory from the path shown above.
This avoids leaving a startup rule that points to a removed skill. To restore a
backup, restore it to the original path after removing the replacement. Restart
the agent after changing startup instructions.

For a plugin installation, use Claude Code's `/plugin` interface to update or
uninstall `skill-mas`; do not manage the plugin cache with the copy installer.

## Troubleshooting

- **Skill missing:** check the scope, target project, and the presence of both
  `SKILL.md` and `references/` in the destination, then restart the agent.
- **Two entries:** remove either the copied Claude skill or the plugin install.
  Also check for an older project-scoped copy shadowing a user installation.
- **No parallel execution:** ensure the session provides native subagent tools.
  The skill cannot add a missing tool; the sequential fallback remains usable.
- **Default routing missing:** start a fresh session, inspect the active Codex
  instruction file or Claude rule, and check for more specific conflicting project
  instructions. For a plugin, check that its SessionStart hook is enabled. Claude
  `--bare` or disabled hooks skip plugin startup routing. Instruction size limits
  or host settings that disable skills can also prevent automatic use.
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
Default routing uses [Codex project instructions](https://developers.openai.com/codex/guides/agents-md),
[Claude rules](https://code.claude.com/docs/en/memory#user-level-rules), and
[SessionStart hooks](https://code.claude.com/docs/en/hooks#sessionstart-decision-control).
