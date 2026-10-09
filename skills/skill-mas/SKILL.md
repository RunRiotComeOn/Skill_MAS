---
name: skill-mas
description: "Orchestrate everyday multi-step coding, research, search, reasoning, and tool tasks by automatically selecting the appropriate optimized Skill-MAS strategy. Compose it with available specialist or orchestration skills, delegate independent work when useful, and verify the result."
---

# Skill-MAS

Apply **task decomposition → agent engineering → workflow orchestration** inside
the current agent session. Complete the user's requested task and deliverable.
Generate a separate MAS program only when the user asks for one.

## Automatic use and skill composition

Use this policy during ordinary task planning. Select the appropriate optimized
skill profile from the current task. For a simple question or single small edit,
answer or edit directly. For a substantive task, load the relevant strategy below
and scale delegation to the work. Respect requests to
skip Skill-MAS, avoid delegation, or follow a specific workflow.

Check the session's available skills and repository instructions for the current
task. Use relevant specialist skills for implementation, research, documents,
testing, or other domain work; Skill-MAS supplies decomposition, context handoffs,
and verification. Load only skills needed for this task, and follow their real
interfaces rather than assuming a skill or tool exists.

Keep **one orchestration owner**. If an existing or user-selected orchestration
skill already coordinates the work, let it own the plan and scheduling, and use
the selected Skill-MAS profile to improve its handoff and verification checks.
Otherwise, coordinate in the main agent and delegate specialist work. Do not
start a second competing plan, duplicate an existing team, or create a cycle of
skills invoking one another. Give subagents a bounded assignment and the relevant
profile/specialist guidance; they should not restart whole-task orchestration.

Choose profiles from the task and communicate useful progress in the host's normal
style. Keep tool actions, material uncertainty, and permission requests visible.

This is a portable adaptation of the four evolved skills in
[Skill_MAS/optimized_skill](https://github.com/linhh29/Skill_MAS/tree/main/optimized_skill).
The references below contain the adapted strategies and identify their sources;
they do not require the research runtime or benchmark datasets.

## Choose a profile

Select by the task shape automatically. Honor an explicit `profile=drb`,
`profile=hlemath`, `profile=bcp`, or `profile=vitabench` if the user supplies one.
Read the selected reference before planning. For a mixed task, use one primary
profile and read another only for a branch that needs it.

| Profile | Best fit | Read |
| --- | --- | --- |
| `drb` | Research reports or comparative analysis with independent perspectives | [references/drb.md](references/drb.md) |
| `hlemath` | Mathematical or logical problems where interpretation and verification matter | [references/hlemath.md](references/hlemath.md) |
| `bcp` | Finding an entity or answer from several clues and source constraints | [references/bcp.md](references/bcp.md) |
| `vitabench` | Multi-step tool work with selection, dependencies, and state changes | [references/vitabench.md](references/vitabench.md) |

For other tasks, including software implementation, use the three stages below
and only the profile patterns that fit. A small, indivisible task can stay with
the main agent.

## 1. Task decomposition: what

- Establish the requested outcome, constraints, inputs, and observable success
  criteria. Resolve material ambiguities before branches depend on them.
- Separate independent work from steps that need earlier results. For each node,
  record its input, expected output, dependencies, and acceptance check.
- Choose the smallest useful team. Prefer a scope → parallel branches → synthesis
  structure for independent analysis; preserve real dependencies for tool work.
  Start with at most four parallel branches, bounded by the host's actual limits
  and the user's budget. Reduce the team when delegation overhead dominates.

## 2. Agent engineering: who

Give each delegated task a concrete contract:

```text
Role and objective:
Inputs: task context, agreed assumptions, relevant sources/files, prerequisites
Scope: owned subtask or files; boundaries with other agents
Available tools: only tools exposed to this agent
Return: result; evidence or artifact paths; checks performed; unresolved gaps
Acceptance check and stopping condition:
```

Pass the relevant profile instructions explicitly: do not assume a child inherits
this skill or the main conversation. Give verifiers access to the evidence and,
when available, independent retrieval or execution tools. Assign disjoint write
ownership when agents share files; the main agent integrates overlapping changes.

## 3. Workflow orchestration: how

- **Codex:** use the session's exposed agent spawn, communication, and wait tools.
  **Claude Code:** use its available subagent/Agent facility. Tool names and
  concurrency differ by version; inspect the host's actual capabilities.
  Keep coordination in the main agent so nested delegation is not required.
- If delegation is unavailable, perform the same roles sequentially in the main
  session and state this limitation. Never describe simulated roles as independent
  agents. Do not start external LLM runtimes or change host settings to compensate.
- Launch independent nodes together. Wait for prerequisite results before
  dependent nodes. Maintain compact shared notes of constraints, verified results,
  evidence pointers, and open gaps; pass only relevant context to each branch.
- Validate handoffs against their acceptance checks. On a substantive failure,
  send targeted feedback to the responsible agent; allow at most two corrective
  attempts per failed node within the remaining budget. Preserve useful partial
  evidence and report unresolved gaps when recovery is exhausted.
- Before synthesis, check coverage against the original requirements and reconcile
  conflicting claims with evidence. Verify changed code with appropriate checks.
  Return one coherent deliverable in the user's requested language and format,
  with material limitations and evidence where relevant.

## Adaptation boundaries

The evolved files were optimized for benchmark-specific MAS generation. Here,
native agent calls replace generated Python orchestration. Size outputs to the
task and budget; benchmark token floors and length-based pass rules do not apply.
Unknown facts remain unknown: never invent data, citations, tool results, or
execution success to fill a contract. Label estimates only when they are useful
and justified. Use the user's requested answer format, including boxed answers
only when appropriate. Existing user authorization, repository instructions,
and host permissions govern tool actions; installing this skill adds no tools
or execution permissions.
