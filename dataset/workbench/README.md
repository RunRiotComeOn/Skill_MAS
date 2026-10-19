# WorkBench backend (transfer evaluation)

Vendored from [olly-styles/WorkBench](https://github.com/olly-styles/WorkBench) (commit in `wb/UPSTREAM_COMMIT`, MIT licence in `wb/LICENSE`): the tools, sandbox CSVs, current (v2) task/outcome files and the official state-based grader (`is_correct`, `has_side_effects`).

`run_eval.py` runs either
- `--mode single`: one native tool-calling agent (same loop as WorkBench's `run_agent_structured`, `act_without_confirmation=True`, all tools), or
- `--mode skill --skill <SKILL.md>`: the Skill-MAS three-stage build with `dataset_name="workbench"`. Sub-agents in the new `env_tool` mode run that same tool loop on one shared per-task sandbox; `llm_only` nodes are allowed for pure reasoning.

Grading executes the recorded tool calls against a fresh sandbox, exactly like WorkBench. Tasks are sampled per domain with a fixed seed (`--n-per-domain`, `--seed`).
