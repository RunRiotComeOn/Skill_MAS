"""Classify WorkBench failures: no write action, wrong/extra writes, or missed some writes."""
import json, sys
from pathlib import Path
sys.path.insert(0, "Skill_MAS/dataset/workbench/wb")
from src.tools.toolkits import tools_with_side_effects
W = {t.name for t in tools_with_side_effects}
fn = lambda a: ".".join(a.split("(")[0].split(".")[:2])
for n in sys.argv[1:]:
    c = {"no_write": 0, "harmful_side_effect": 0, "other_wrong": 0}; calls = 0; llm_nodes = 0; nodes = 0
    rs = [json.loads(p.read_text()) for p in Path(f"results/wb/{n}/tasks").glob("*.json")]
    for r in rs:
        writes = [a for a in r["function_calls"] if fn(a) in W]
        calls += len(r["function_calls"])
        modes = r.get("execution_modes") or []
        nodes += len(modes); llm_nodes += sum(m == "llm_only" for m in modes)
        if r["correct"]: continue
        if r["ground_truth"] and not writes: c["no_write"] += 1
        elif r["side_effects"]: c["harmful_side_effect"] += 1
        else: c["other_wrong"] += 1
    print(f"{n:15s} wrong={sum(c.values()):3d} {c} tool_calls/task={calls/len(rs):.1f} agents/task={nodes/len(rs):.1f} llm_only_share={llm_nodes/max(1,nodes):.2f}")
