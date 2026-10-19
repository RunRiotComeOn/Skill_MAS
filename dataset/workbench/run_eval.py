"""WorkBench evaluation for Skill-MAS skills and a single-agent tool-calling baseline.

WorkBench (olly-styles/WorkBench, vendored under ``wb/``) grades a task by executing the
agent's write actions against a fresh sandbox and comparing the final database state with
the ground truth. Every sub-agent that runs in ``env_tool`` mode shares one per-task sandbox,
so the actions of the whole multi-agent workflow are graded together.

Usage (from the parent of Skill_MAS/):
  python -m Skill_MAS.dataset.workbench.run_eval --mode skill --skill Skill_MAS/init_skill/SKILL.md --out results/wb_init
  python -m Skill_MAS.dataset.workbench.run_eval --mode single --out results/wb_single
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import contextvars
import json
import random
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WB_ROOT = Path(__file__).resolve().parent / "wb"
sys.path.insert(0, str(WB_ROOT))

import pandas as pd  # noqa: E402
from src.tools import state as wb_state  # noqa: E402

wb_state._CSV_PATHS = {k: str(WB_ROOT / v) for k, v in wb_state._CSV_PATHS.items()}

from src.data_generation.data_generation_utils import HARDCODED_CURRENT_TIME  # noqa: E402
from src.evals.actions import convert_intermediate_step_to_function_call  # noqa: E402
from src.evals.evaluation import has_side_effects, is_correct  # noqa: E402
from src.tools.tool import tool_to_openai_schema  # noqa: E402
from src.tools.toolkits import all_tools  # noqa: E402

from Skill_MAS.skill_mas.build import (  # noqa: E402
    generate_mas_artifacts_with_retries,
    make_planner_call_fn,
    make_text_call_fn,
    run_generated_workflow_with_retries,
)
from Skill_MAS.skill_mas.openai_async_client import (  # noqa: E402
    AsyncOpenAIClient,
    _usage_dict_from_chat_completion,
    enrich_usage_with_cost,
)

DOMAINS = [
    "email",
    "calendar",
    "analytics",
    "project_management",
    "customer_relationship_manager",
    "multi_domain",
]
TASKS_DIR = WB_ROOT / "data" / "processed" / "tasks_and_outcomes"

# Same wording as WorkBench's inference.py / agent.py (act_without_confirmation=True).
DATETIME_PREFIX = (
    f"Today's date is {HARDCODED_CURRENT_TIME.strftime('%A')}, {HARDCODED_CURRENT_TIME.date()} "
    f"and the current time is {HARDCODED_CURRENT_TIME.time()}. "
    f"Remember the current date and time when completing tasks. "
    f"Meetings must not start before 9am or end after 6pm."
)
ACT_WITHOUT_CONFIRMATION_SUFFIX = (
    " Do not ask for confirmation before executing actions."
    " Execute actions immediately and continue until the task is fully complete."
    " Do not stop after a search or lookup step."
)
SYSTEM_PROMPT = DATETIME_PREFIX + ACT_WITHOUT_CONFIRMATION_SUFFIX

MAX_TOOL_ITERATIONS = 20
MAX_OBSERVATION_CHARS = 6000

_SANITIZED = {t.name.replace(".", "__"): t for t in all_tools}
_TOOL_SCHEMAS = []
for _name, _t in _SANITIZED.items():
    _s = tool_to_openai_schema(_t)
    _s["function"]["name"] = _name
    _TOOL_SCHEMAS.append(_s)

_usage_acc: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("wb_usage_acc", default=None)


def _add_usage(u: dict[str, Any]) -> None:
    acc = _usage_acc.get()
    if acc is None:
        return
    acc["calls"] = acc.get("calls", 0) + 1
    for k in ("input_tokens", "output_tokens", "total_tokens"):
        acc[k] = acc.get(k, 0) + int(u.get(k, 0) or 0)
    acc["estimated_cost_usd"] = acc.get("estimated_cost_usd", 0.0) + float(u.get("estimated_cost_usd", 0.0) or 0.0)


class CountingClient(AsyncOpenAIClient):
    """AsyncOpenAIClient that records every call's usage into the current task's accumulator."""

    served_models: set[str] = set()

    async def generate(self, **kw: Any) -> tuple[str, dict[str, Any]]:
        text, usage = await super().generate(**kw)
        _add_usage(usage)
        return text, usage


@dataclass
class WBTask:
    uid: str
    domain: str
    index: int
    task: str
    outcome: list[str]


@dataclass
class Sandbox:
    """One task's WorkBench sandbox, shared by every env_tool sub-agent of a workflow."""

    state: Any = field(default_factory=lambda: wb_state._pristine_state().copy())
    function_calls: list[str] = field(default_factory=list)

    def call(self, sanitized_name: str, args: dict[str, Any]) -> str:
        t = _SANITIZED.get(sanitized_name)
        if t is None:
            return f"Tool '{sanitized_name}' not found."
        str_args = {k: str(v) for k, v in (args or {}).items()}
        self.function_calls.append(convert_intermediate_step_to_function_call(t.name, str_args))
        # Tools read the thread-local state; no await happens between this swap and the call.
        wb_state._local.tool_state = self.state
        try:
            return str(t(**str_args))
        except Exception as e:  # tools raise on bad arguments; surface it like WorkBench does
            return f"Error: {type(e).__name__}: {e}"


def load_tasks(n_per_domain: int, seed: int) -> list[WBTask]:
    rng = random.Random(seed)
    out: list[WBTask] = []
    for d in DOMAINS:
        df = pd.read_csv(TASKS_DIR / f"{d}_tasks_and_outcomes.csv")
        idx = list(range(len(df)))
        if n_per_domain > 0:
            idx = sorted(rng.sample(idx, min(n_per_domain, len(idx))))
        for i in idx:
            out.append(
                WBTask(
                    uid=f"{d}_{i}",
                    domain=d,
                    index=i,
                    task=str(df.task[i]),
                    outcome=list(ast.literal_eval(df.outcome[i])),
                )
            )
    return out


async def tool_loop(client: CountingClient, sandbox: Sandbox, prompt: str) -> tuple[str, dict[str, Any], list[dict]]:
    """Native tool-calling loop (mirrors WorkBench run_agent_structured) on the shared sandbox."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    usage_total: dict[str, Any] = {}
    steps: list[dict] = []
    for _ in range(MAX_TOOL_ITERATIONS):
        resp = await client.client.chat.completions.create(
            model=client.model,
            messages=messages,
            tools=_TOOL_SCHEMAS,
            temperature=0,
            max_tokens=8192,
        )
        CountingClient.served_models.add(str(getattr(resp, "model", "")))
        u = enrich_usage_with_cost(_usage_dict_from_chat_completion(resp), model=client.model, table=client.pricing)
        _add_usage(u)
        for k in ("input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd"):
            usage_total[k] = usage_total.get(k, 0) + (u.get(k, 0) or 0)
        msg = resp.choices[0].message
        tcs = msg.tool_calls or []
        if not tcs:
            return (msg.content or "").strip(), usage_total, steps
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in tcs
                ],
            }
        )
        for tc in tcs:
            try:
                args = json.loads(tc.function.arguments or "{}")
                if not isinstance(args, dict):
                    args = {}
            except json.JSONDecodeError:
                args = {}
            obs = sandbox.call(tc.function.name, args)
            steps.append({"tool": tc.function.name, "args": args, "observation": obs[:500]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": obs[:MAX_OBSERVATION_CHARS]})
    return "Agent stopped due to iteration limit.", usage_total, steps


def _actions_note(steps: list[dict]) -> str:
    if not steps:
        return "(no tool calls)"
    return "\n".join(f"- {s['tool'].replace('__', '.')}({json.dumps(s['args'], ensure_ascii=False)}) -> {s['observation'][:200]}" for s in steps)


async def run_single(client: CountingClient, task: WBTask, sandbox: Sandbox) -> dict[str, Any]:
    text, _u, steps = await tool_loop(client, sandbox, task.task)
    return {"final_output": text, "steps": steps}


async def run_skill(client: CountingClient, task: WBTask, sandbox_box: list[Sandbox], skill: Path, exec_attempts: int) -> dict[str, Any]:
    planner_call_fn = make_planner_call_fn(
        client, generation_kwargs={"response_format": {"type": "json_object"}, "temperature": 0.2}
    )
    text_call_fn = make_text_call_fn(client)
    class_name = f"WorkBenchTask_{task.uid}_MASWorkflow"
    task_text = DATETIME_PREFIX + "\n\n" + task.task
    artifacts, gen_attempts, gen_events = await generate_mas_artifacts_with_retries(
        task_text=task_text,
        class_name=class_name,
        init_skill_path=skill,
        planner_call_fn=planner_call_fn,
        max_attempts=5,
        dataset_name="workbench",
    )
    if artifacts is None:
        return {"final_output": "", "error": "generation_failed", "events": gen_events}

    node_logs: list[dict] = []

    async def tool_call_fn(payload: Any) -> tuple[str, dict[str, Any]]:
        prompt = payload.get("prompt") if isinstance(payload, dict) else str(payload)
        role = payload.get("role_name") if isinstance(payload, dict) else ""
        text, usage, steps = await tool_loop(client, sandbox_box[0], prompt)
        node_logs.append({"role": role, "steps": steps, "output": text[:2000]})
        # Downstream agents see what this node actually executed, not only its prose.
        return f"{text}\n\n[Tool calls executed by this agent]\n{_actions_note(steps)}", usage

    ok, state, final_code, err = False, {}, artifacts.mas_code, None
    for attempt in range(max(1, exec_attempts)):
        if attempt > 0:  # a crashed workflow may have written to the sandbox; start clean
            sandbox_box[0] = Sandbox()
            node_logs.clear()
        ok, state, final_code, _n, _ev, err = await run_generated_workflow_with_retries(
            mas_code=artifacts.mas_code,
            class_name=class_name,
            task_text=task_text,
            text_call_fn=text_call_fn,
            planner_call_fn=planner_call_fn,
            tool_call_fn=tool_call_fn,
            max_attempts=1,
            dataset_name="workbench",
        )
        if ok:
            break
    def _get(s: Any, k: str) -> Any:
        return s.get(k) if isinstance(s, dict) else getattr(s, k, None)

    subs = artifacts.normalized_sub_agents or []
    modes = [dict(_get(s, "tool_context") or {}).get("execution_mode") for s in subs]
    return {
        "final_output": str((state or {}).get("final_output", "") or ""),
        "error": None if ok else (err or "execution_failed"),
        "mas_code": final_code,
        "sub_agents": [_get(s, "role_name") for s in subs],
        "execution_modes": modes,
        "node_logs": node_logs,
        "generation_attempts": gen_attempts,
    }


async def run_one(args: argparse.Namespace, client: CountingClient, task: WBTask, out_dir: Path, sem: asyncio.Semaphore) -> dict[str, Any] | None:
    path = out_dir / "tasks" / f"{task.uid}.json"
    if path.exists():
        return json.loads(path.read_text())
    async with sem:
        acc: dict[str, Any] = {}
        _usage_acc.set(acc)
        sandbox_box = [Sandbox()]
        t0 = time.time()
        try:
            if args.mode == "single":
                rec = await run_single(client, task, sandbox_box[0])
            else:
                rec = await run_skill(client, task, sandbox_box, Path(args.skill), args.exec_attempts)
        except Exception as e:
            rec = {"final_output": "", "error": f"exception: {type(e).__name__}: {e}", "traceback": traceback.format_exc()}
        calls = sandbox_box[0].function_calls
        correct = is_correct(calls, task.outcome, "")
        side = has_side_effects(calls, correct)
        rec.update(
            {
                "uid": task.uid,
                "domain": task.domain,
                "task": task.task,
                "ground_truth": task.outcome,
                "function_calls": calls,
                "correct": bool(correct),
                "side_effects": bool(side),
                "usage": acc,
                "elapsed_s": round(time.time() - t0, 2),
            }
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=2, default=str))
        print(f"[wb] {task.uid} correct={correct} side_effects={side} cost=${acc.get('estimated_cost_usd', 0):.4f}", flush=True)
        return rec


def summarize(recs: list[dict], args: argparse.Namespace) -> dict[str, Any]:
    by: dict[str, list[dict]] = {}
    for r in recs:
        by.setdefault(r["domain"], []).append(r)

    def agg(rs: list[dict]) -> dict[str, Any]:
        n = len(rs)
        return {
            "n": n,
            "accuracy": round(sum(r["correct"] for r in rs) / n, 4) if n else None,
            "side_effect_rate": round(sum(r["side_effects"] for r in rs) / n, 4) if n else None,
            "errors": sum(1 for r in rs if r.get("error")),
            "cost_usd": round(sum(float(r.get("usage", {}).get("estimated_cost_usd", 0)) for r in rs), 4),
        }

    return {
        "mode": args.mode,
        "skill": args.skill,
        "model": args.model,
        "served_models": sorted(CountingClient.served_models),
        "n_per_domain": args.n_per_domain,
        "seed": args.seed,
        "overall": agg(recs),
        "by_domain": {d: agg(by[d]) for d in DOMAINS if d in by},
    }


async def main_async(args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks(args.n_per_domain, args.seed)
    if args.limit:
        tasks = tasks[: args.limit]
    (out_dir / "task_ids.json").write_text(json.dumps([t.uid for t in tasks]))
    client = CountingClient(model=args.model)
    sem = asyncio.Semaphore(args.max_concurrency)
    recs = await asyncio.gather(*(run_one(args, client, t, out_dir, sem) for t in tasks))
    summary = summarize([r for r in recs if r], args)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("single", "skill"), required=True)
    p.add_argument("--skill", default="")
    p.add_argument("--model", default="deepseek-chat")
    p.add_argument("--n-per-domain", type=int, default=15, help="tasks sampled per domain (0 = all 690)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--max-concurrency", type=int, default=8)
    p.add_argument("--exec-attempts", type=int, default=3)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    if args.mode == "skill" and not args.skill:
        p.error("--skill is required for --mode skill")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
